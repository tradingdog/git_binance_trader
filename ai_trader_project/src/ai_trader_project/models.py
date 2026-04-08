from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from pydantic import BaseModel, Field


class StrategyStatus(str, Enum):
    running = "running"
    paused = "paused"
    halted = "halted"


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
    status: str
    created_at: datetime
    summary: str
    steps: list[str] = Field(default_factory=list)


class HumanCommand(BaseModel):
    command: str
    operator: str = "human"


class MemoryEntry(BaseModel):
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    event_type: str
    actor: str
    message: str
    meta: dict[str, object] = Field(default_factory=dict)
