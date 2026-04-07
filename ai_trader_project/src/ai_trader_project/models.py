from __future__ import annotations

from datetime import datetime, timezone
from pydantic import BaseModel, Field


class ControlState(BaseModel):
    status: str = "running"
    equity: float
    drawdown_pct: float
    daily_drawdown_pct: float
    positions: int
    ai_message: str = "系统已启动"
    ai_insight: str = "等待下一轮"
    generated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class HumanCommand(BaseModel):
    command: str
    operator: str = "human"


class MemoryEntry(BaseModel):
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    event_type: str
    actor: str
    message: str
    meta: dict[str, object] = Field(default_factory=dict)
