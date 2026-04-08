from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from pydantic import BaseModel, Field


class StrategyStatus(str, Enum):
    running = "running"
    paused = "paused"
    halted = "halted"


class AutonomyLevel(str, Enum):
    l1_observe = "L1"
    l2_semiauto = "L2"
    l3_controlled_auto = "L3"
    l4_full_auto = "L4"


class UserRole(str, Enum):
    human_root = "human_root"
    researcher_ai = "researcher_ai"
    validator_ai = "validator_ai"
    releaser_ai = "releaser_ai"
    viewer = "viewer"


class TaskStatus(str, Enum):
    pending = "pending"
    running = "running"
    failed = "failed"
    completed = "completed"


class ApprovalStatus(str, Enum):
    pending = "pending"
    approved = "approved"
    rejected = "rejected"


class MarketType(str, Enum):
    spot = "spot"
    perpetual = "perpetual"
    alpha = "alpha"


class Side(str, Enum):
    buy = "buy"
    sell = "sell"


class ControlState(BaseModel):
    status: StrategyStatus = StrategyStatus.running
    equity: float
    cash: float
    margin_used: float
    position_value: float
    fees_paid: float
    realized_pnl: float
    unrealized_pnl: float
    total_return_pct: float
    drawdown_pct: float
    daily_drawdown_pct: float
    positions: int
    ai_message: str = "系统已启动"
    ai_insight: str = "等待下一轮"
    generated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class RiskConstraints(BaseModel):
    max_drawdown_pct: float = 15.0
    max_daily_drawdown_pct: float = 5.0
    max_trade_loss_pct: float = 1.0
    simulation_only: bool = True


class ObjectiveWeights(BaseModel):
    w1_day_return: float = 1.0
    w2_sharpe: float = 0.8
    w3_mdd: float = 0.9
    w4_fee_ratio: float = 0.7
    w5_turnover_penalty: float = 0.6


class GovernanceConfig(BaseModel):
    autonomy_level: AutonomyLevel = AutonomyLevel.l2_semiauto
    allow_structural_changes: bool = False
    allow_night_autonomy: bool = False
    objective_daily_return_pct: float = 1.0
    max_fee_ratio_pct: float = 35.0
    risk: RiskConstraints = Field(default_factory=RiskConstraints)
    objective_weights: ObjectiveWeights = Field(default_factory=ObjectiveWeights)


class StrategyCandidate(BaseModel):
    id: str
    created_at: datetime
    name: str
    source: str = "research_agent"
    day_return_pct: float
    sharpe: float
    mdd_pct: float
    fee_ratio_pct: float
    turnover_penalty: float
    score_j: float
    hard_constraint_passed: bool
    risk_note: str
    status: str


class PositionSnapshot(BaseModel):
    symbol: str
    market_type: MarketType
    side: Side
    leverage: int
    quantity: float
    entry_price: float
    current_price: float
    stop_loss: float
    take_profit: float
    unrealized_pnl: float


class TradeSnapshot(BaseModel):
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    symbol: str
    market_type: MarketType
    side: Side
    quantity: float
    price: float
    fee_paid: float
    realized_pnl: float
    note: str = "simulation"


class TokenUsageSnapshot(BaseModel):
    model_name: str
    input_tokens: int = 0
    output_tokens: int = 0
    cached_tokens: int = 0
    input_cost_usd: float = 0.0
    output_cost_usd: float = 0.0
    cache_cost_usd: float = 0.0

    @property
    def total_tokens(self) -> int:
        return self.input_tokens + self.output_tokens + self.cached_tokens

    @property
    def total_cost_usd(self) -> float:
        return self.input_cost_usd + self.output_cost_usd + self.cache_cost_usd


class TaskDetail(BaseModel):
    id: str
    title: str
    status: TaskStatus
    created_at: datetime
    summary: str
    steps: list[str] = Field(default_factory=list)


class ApprovalItem(BaseModel):
    id: str
    created_at: datetime
    action: str
    reason: str
    requested_by: str
    status: ApprovalStatus = ApprovalStatus.pending
    decided_by: str = ""
    decided_at: datetime | None = None
    payload: dict[str, object] = Field(default_factory=dict)


class ReleaseState(BaseModel):
    champion_version: str = "champion-v1"
    challenger_version: str = ""
    gray_ratio_pct: float = 0.0
    auto_expand_enabled: bool = False
    last_release_at: datetime | None = None
    last_rollback_at: datetime | None = None
    status: str = "stable"


class AuditEvent(BaseModel):
    id: str
    created_at: datetime
    category: str
    actor: str
    message: str
    detail: dict[str, object] = Field(default_factory=dict)


class HumanCommand(BaseModel):
    command: str
    operator: str = "human"


class ActionRequest(BaseModel):
    operator: str = "human"
    role: UserRole = UserRole.human_root


class ConfigPatchRequest(BaseModel):
    operator: str = "human"
    role: UserRole = UserRole.human_root
    autonomy_level: AutonomyLevel | None = None
    allow_structural_changes: bool | None = None
    allow_night_autonomy: bool | None = None
    objective_daily_return_pct: float | None = None
    max_fee_ratio_pct: float | None = None


class ApprovalDecisionRequest(BaseModel):
    operator: str = "human"
    role: UserRole = UserRole.human_root
    decision: str


class MemoryEntry(BaseModel):
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    event_type: str
    actor: str
    message: str
    meta: dict[str, object] = Field(default_factory=dict)
