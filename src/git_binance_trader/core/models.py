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


class Position(BaseModel):
    symbol: str
    quantity: float
    entry_price: float
    current_price: float
    market_type: MarketType
    stop_loss: float
    take_profit: float
    highest_price: float
    risk_budget_pct: float = 0.35

    @property
    def market_value(self) -> float:
        return self.quantity * self.current_price

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
    strategy_insight: str = ""
    generated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
