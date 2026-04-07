from __future__ import annotations

import asyncio
from datetime import datetime, timezone

from ai_trader_project.config import Settings
from ai_trader_project.memory import MemoryStore
from ai_trader_project.models import ControlState


class GovernanceEngine:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.memory = MemoryStore(settings)
        self.state = ControlState(
            equity=settings.initial_balance_usdt,
            drawdown_pct=0.0,
            daily_drawdown_pct=0.0,
            positions=0,
        )
        self._runner: asyncio.Task[None] | None = None
        self._tick = 0

    async def start(self) -> None:
        if self._runner is None or self._runner.done():
            self._runner = asyncio.create_task(self._loop())
            self.memory.append_ai("system", "ai_core", "AI治理引擎启动")

    async def stop(self) -> None:
        if self._runner is not None:
            self._runner.cancel()
            try:
                await self._runner
            except asyncio.CancelledError:
                pass
            self._runner = None
            self.memory.append_ai("system", "ai_core", "AI治理引擎停止")

    async def _loop(self) -> None:
        while True:
            self._tick += 1
            if self.state.status == "running":
                drift = ((self._tick % 7) - 3) * 0.12
                self.state.equity = max(1000.0, self.state.equity + drift)
                peak = max(self.settings.initial_balance_usdt, self.state.equity)
                self.state.drawdown_pct = max(0.0, (peak - self.state.equity) / peak * 100)
                self.state.daily_drawdown_pct = min(5.0, self.state.drawdown_pct * 0.7)
                self.state.positions = max(0, (self._tick % 4))
                self.state.ai_insight = f"AI轮询第{self._tick}次，执行模拟策略评估"
                self.state.ai_message = "AI完成一轮自检与风险评估"
                self.state.generated_at = datetime.now(timezone.utc)
                self.memory.append_ai(
                    "ai_cycle",
                    "ai_core",
                    self.state.ai_message,
                    {
                        "equity": round(self.state.equity, 4),
                        "drawdown_pct": round(self.state.drawdown_pct, 4),
                        "positions": self.state.positions,
                    },
                )
            await asyncio.sleep(self.settings.cycle_interval_seconds)

    async def snapshot(self) -> ControlState:
        return self.state

    async def pause(self) -> dict[str, str]:
        self.state.status = "paused"
        self.state.ai_message = "人工触发全面暂停"
        self.memory.append_ai("human_action", "human", "全面暂停", {"status": self.state.status})
        return {"status": self.state.status, "message": self.state.ai_message}

    async def resume(self) -> dict[str, str]:
        self.state.status = "running"
        self.state.ai_message = "人工触发恢复自动交易"
        self.memory.append_ai("human_action", "human", "恢复自动交易", {"status": self.state.status})
        return {"status": self.state.status, "message": self.state.ai_message}

    async def emergency_close(self) -> dict[str, str]:
        self.state.positions = 0
        self.state.status = "paused"
        self.state.ai_message = "人工触发全面平仓并暂停"
        self.memory.append_ai("human_action", "human", "全面平仓并暂停", {"status": self.state.status})
        return {"status": self.state.status, "message": self.state.ai_message}

    async def halt(self) -> dict[str, str]:
        self.state.positions = 0
        self.state.status = "halted"
        self.state.ai_message = "人工触发全面停止"
        self.memory.append_ai("human_action", "human", "全面停止", {"status": self.state.status})
        return {"status": self.state.status, "message": self.state.ai_message}

    async def record_command(self, operator: str, command: str) -> dict[str, object]:
        cmd = self.memory.append_command(operator=operator, command=command)
        return {"status": "ok", "message": "命令已写入AI记忆", "command": cmd}

    async def governance_payload(self) -> dict[str, object]:
        state = await self.snapshot()
        return {
            "human_version": {
                "name": "human",
                "app": "git-binance-trader-sim",
                "dashboard_url": "https://git-binance-trader-sim.fly.dev/",
            },
            "ai_version": {
                "name": "ai",
                "app": "git-binance-trader-ai",
                "dashboard_url": "https://git-binance-trader-ai.fly.dev/",
            },
            "system": {
                "status": state.status,
                "equity": state.equity,
                "drawdown_pct": state.drawdown_pct,
                "daily_drawdown_pct": state.daily_drawdown_pct,
                "positions": state.positions,
                "ai_message": state.ai_message,
                "ai_insight": state.ai_insight,
                "last_cycle_at": state.generated_at.isoformat(),
            },
            "memory": self.memory.recent_ai(limit=80),
            "commands": self.memory.recent_commands(limit=30),
        }
