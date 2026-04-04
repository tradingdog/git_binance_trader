from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from pydantic import BaseModel, Field


class MarketType(str, Enum):
    spot = "spot"
    perpetual = "perpetual"
    alpha = "alpha"


class Side(str, Enum):
    buy = "buy"
    sell = "sell"


class StrategyState(str, Enum):
    running = "running"
    paused = "paused"
    halted = "halted"


class SymbolSnapshot(BaseModel):
    symbol: str
    price: float
    market_cap_rank: int
    volume_24h: float
    change_pct_24h: float
    market_type: MarketType = MarketType.spot
    leverage: int = 1
    data_source: str = "binance-spot"


class EquityPoint(BaseModel):
    timestamp: datetime
    equity: float
    cash: float
    margin_used: float
    position_value: float


class StorageStatus(BaseModel):
    path: str
    total_mb: float
    free_mb: float
    min_free_mb: int
    cleanup_required: bool = False


class Position(BaseModel):
    symbol: str
    quantity: float
    entry_price: float
    current_price: float
    market_type: MarketType
    leverage: int = 1
    stop_loss: float
    take_profit: float
    highest_price: float
    risk_budget_pct: float = 0.35

    @property
    def market_value(self) -> float:
        return self.quantity * self.current_price

    @property
    def margin_used(self) -> float:
        leverage = max(self.leverage, 1)
        return self.quantity * self.entry_price / leverage

    @property
    def unrealized_pnl(self) -> float:
        return (self.current_price - self.entry_price) * self.quantity


class Trade(BaseModel):
    symbol: str
    side: Side
    quantity: float
    price: float
    realized_pnl: float = 0.0
    market_type: MarketType
    leverage: int = 1
    strategy: str
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    note: str = "simulation"


class RiskStatus(BaseModel):
    max_drawdown_pct: float
    daily_drawdown_pct: float
    single_trade_loss_pct: float
    breached: bool = False
    message: str = "正常"


class AccountSnapshot(BaseModel):
    equity: float
    cash: float
    margin_used: float
    position_value: float
    balance_check_delta: float
    unrealized_pnl: float
    realized_pnl: float
    total_return_pct: float
    drawdown_pct: float
    daily_drawdown_pct: float
    status: StrategyState
    risk_status: RiskStatus


class DashboardState(BaseModel):
    account: AccountSnapshot
    positions: list[Position]
    trades: list[Trade]
    watchlist: list[SymbolSnapshot]
    equity_history: list[EquityPoint] = Field(default_factory=list)
    storage: StorageStatus | None = None
    strategy_insight: str = ""
    generated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
