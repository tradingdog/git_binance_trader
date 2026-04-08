from __future__ import annotations

import asyncio
import random
from collections import deque
from datetime import datetime, timezone

from .config import Settings
from .memory import MemoryStore
from .models import (
    ControlState,
    MarketType,
    PositionSnapshot,
    Side,
    StrategyStatus,
    TaskDetail,
    TokenUsageSnapshot,
    TradeSnapshot,
)


class GovernanceEngine:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.memory = MemoryStore(settings)
        self._rng = random.Random(20260408)
        self._position_book: dict[str, PositionSnapshot] = {}
        self._trades: deque[TradeSnapshot] = deque(maxlen=800)
        self._runtime_logs: deque[str] = deque(maxlen=1500)
        self._tasks: deque[TaskDetail] = deque(maxlen=240)
        self._token_usage = TokenUsageSnapshot(model_name=settings.ai_model_name)
        self._peak_equity = settings.initial_balance_usdt
        self._start_of_day_equity = settings.initial_balance_usdt
        self.state = ControlState(
            equity=settings.initial_balance_usdt,
            cash=settings.initial_balance_usdt,
            margin_used=0.0,
            position_value=0.0,
            fees_paid=0.0,
            realized_pnl=0.0,
            unrealized_pnl=0.0,
            total_return_pct=0.0,
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
            if self.state.status == StrategyStatus.running:
                self._simulate_cycle()
            await asyncio.sleep(self.settings.cycle_interval_seconds)

    async def snapshot(self) -> ControlState:
        return self.state

    def _simulate_cycle(self) -> None:
        now_ts = datetime.now(timezone.utc)
        cycle_actions: list[str] = []

        for symbol, position in list(self._position_book.items()):
            change_ratio = self._rng.uniform(-0.015, 0.02)
            next_price = max(0.1, position.current_price * (1 + change_ratio))
            unrealized = (next_price - position.entry_price) * position.quantity
            position.current_price = round(next_price, 4)
            position.unrealized_pnl = round(unrealized, 4)
            self._position_book[symbol] = position

        if len(self._position_book) < 4 and self._tick % 3 == 0:
            self._open_mock_position(cycle_actions)

        if self._position_book and self._tick % 4 == 0:
            self._close_mock_position(cycle_actions)

        self._apply_token_usage(cycle_actions)
        self._refresh_account(now_ts, cycle_actions)

    def _open_mock_position(self, cycle_actions: list[str]) -> None:
        candidates = [
            ("BTCUSDT", MarketType.spot, 1),
            ("ETHUSDT", MarketType.spot, 1),
            ("SOLUSDT", MarketType.perpetual, 3),
            ("DOGEUSDT", MarketType.perpetual, 3),
            ("AIUSDT", MarketType.alpha, 2),
            ("WLDUSDT", MarketType.alpha, 2),
        ]
        available = [item for item in candidates if item[0] not in self._position_book]
        if not available:
            return
        symbol, market_type, leverage = self._rng.choice(available)
        price = round(self._rng.uniform(8, 160), 4)
        quantity = round(self._rng.uniform(0.4, 1.8), 6)
        margin = price * quantity / max(1, leverage)
        entry_fee = margin * 0.0012
        if self.state.cash <= margin + entry_fee:
            return

        self.state.cash = round(self.state.cash - margin - entry_fee, 4)
        self.state.fees_paid = round(self.state.fees_paid + entry_fee, 4)
        position = PositionSnapshot(
            symbol=symbol,
            market_type=market_type,
            side=Side.buy,
            leverage=leverage,
            quantity=quantity,
            entry_price=price,
            current_price=price,
            stop_loss=round(price * 0.97, 4),
            take_profit=round(price * 1.03, 4),
            unrealized_pnl=0.0,
        )
        self._position_book[symbol] = position
        self._trades.appendleft(
            TradeSnapshot(
                symbol=symbol,
                market_type=market_type,
                side=Side.buy,
                quantity=quantity,
                price=price,
                fee_paid=round(entry_fee, 4),
                realized_pnl=0.0,
                note="AI开仓",
            )
        )
        cycle_actions.append(f"新开仓 {symbol} {market_type.value} 数量{quantity:.4f}")

    def _close_mock_position(self, cycle_actions: list[str]) -> None:
        symbol = self._rng.choice(list(self._position_book.keys()))
        position = self._position_book[symbol]
        exit_price = round(position.current_price * (1 + self._rng.uniform(-0.01, 0.015)), 4)
        gross_pnl = (exit_price - position.entry_price) * position.quantity
        margin = position.entry_price * position.quantity / max(1, position.leverage)
        close_fee = margin * 0.0012
        realized = gross_pnl - close_fee

        self.state.cash = round(self.state.cash + margin + realized, 4)
        self.state.realized_pnl = round(self.state.realized_pnl + realized, 4)
        self.state.fees_paid = round(self.state.fees_paid + close_fee, 4)

        self._trades.appendleft(
            TradeSnapshot(
                symbol=symbol,
                market_type=position.market_type,
                side=Side.sell,
                quantity=position.quantity,
                price=exit_price,
                fee_paid=round(close_fee, 4),
                realized_pnl=round(realized, 4),
                note="AI平仓",
            )
        )
        del self._position_book[symbol]
        cycle_actions.append(f"平仓 {symbol} 已实现{realized:.4f}")

    def _apply_token_usage(self, cycle_actions: list[str]) -> None:
        input_tokens = self._rng.randint(1800, 4200)
        output_tokens = self._rng.randint(450, 1300)
        cached_tokens = self._rng.randint(200, 1600)
        self._token_usage.input_tokens += input_tokens
        self._token_usage.output_tokens += output_tokens
        self._token_usage.cached_tokens += cached_tokens

        self._token_usage.input_cost_usd += input_tokens / 1_000_000 * self.settings.ai_input_price_per_million
        self._token_usage.output_cost_usd += output_tokens / 1_000_000 * self.settings.ai_output_price_per_million
        self._token_usage.cache_cost_usd += cached_tokens / 1_000_000 * self.settings.ai_cache_price_per_million

        cycle_actions.append(
            f"推理消耗 输入{input_tokens} 输出{output_tokens} 缓存{cached_tokens} token"
        )

    def _refresh_account(self, now_ts: datetime, cycle_actions: list[str]) -> None:
        position_value = sum(p.current_price * p.quantity for p in self._position_book.values())
        margin_used = sum(p.entry_price * p.quantity / max(1, p.leverage) for p in self._position_book.values())
        unrealized = sum(p.unrealized_pnl for p in self._position_book.values())

        self.state.margin_used = round(margin_used, 4)
        self.state.position_value = round(position_value, 4)
        self.state.unrealized_pnl = round(unrealized, 4)
        self.state.positions = len(self._position_book)
        self.state.equity = round(self.state.cash + margin_used + unrealized, 4)
        self.state.total_return_pct = round(
            (self.state.equity - self.settings.initial_balance_usdt) / self.settings.initial_balance_usdt * 100,
            4,
        )

        self._peak_equity = max(self._peak_equity, self.state.equity)
        self.state.drawdown_pct = round(max(0.0, (self._peak_equity - self.state.equity) / self._peak_equity * 100), 4)
        self.state.daily_drawdown_pct = round(
            max(0.0, (self._start_of_day_equity - self.state.equity) / self._start_of_day_equity * 100),
            4,
        )

        if not cycle_actions:
            cycle_actions.append("未触发交易动作，持续监控风控与任务队列")
        self.state.ai_insight = f"AI轮询第{self._tick}次，执行 {len(cycle_actions)} 项任务"
        self.state.ai_message = "；".join(cycle_actions[:3])
        self.state.generated_at = now_ts

        task = TaskDetail(
            id=f"task-{self._tick:06d}",
            title=f"第{self._tick}轮：策略评估与执行",
            status="completed",
            created_at=now_ts,
            summary=self.state.ai_message,
            steps=[
                "读取最新账户与持仓状态",
                "计算风险与目标偏移",
                *cycle_actions,
                "写入记忆与审计日志",
            ],
        )
        self._tasks.appendleft(task)
        self._runtime_logs.appendleft(
            f"{now_ts.isoformat()} | status={self.state.status.value} | equity={self.state.equity:.4f} | {self.state.ai_message}"
        )

        self.memory.append_ai(
            "ai_cycle",
            "ai_core",
            self.state.ai_message,
            {
                "equity": self.state.equity,
                "cash": self.state.cash,
                "margin_used": self.state.margin_used,
                "position_value": self.state.position_value,
                "fees_paid": self.state.fees_paid,
                "drawdown_pct": self.state.drawdown_pct,
                "token_total": self._token_usage.total_tokens,
                "token_cost_usd": round(self._token_usage.total_cost_usd, 6),
                "task_id": task.id,
                "actions": cycle_actions,
            },
        )

    async def pause(self) -> dict[str, str]:
        self.state.status = StrategyStatus.paused
        self.state.ai_message = "人工触发全面暂停"
        self.memory.append_ai("human_action", "human", "全面暂停", {"status": self.state.status.value})
        return {"status": self.state.status.value, "message": self.state.ai_message}

    async def resume(self) -> dict[str, str]:
        self.state.status = StrategyStatus.running
        self.state.ai_message = "人工触发恢复自动交易"
        self.memory.append_ai("human_action", "human", "恢复自动交易", {"status": self.state.status.value})
        return {"status": self.state.status.value, "message": self.state.ai_message}

    async def emergency_close(self) -> dict[str, str]:
        for symbol in list(self._position_book.keys()):
            position = self._position_book[symbol]
            self._trades.appendleft(
                TradeSnapshot(
                    symbol=position.symbol,
                    market_type=position.market_type,
                    side=Side.sell,
                    quantity=position.quantity,
                    price=position.current_price,
                    fee_paid=0.0,
                    realized_pnl=round(position.unrealized_pnl, 4),
                    note="人工一键平仓",
                )
            )
            self.state.realized_pnl = round(self.state.realized_pnl + position.unrealized_pnl, 4)
            margin = position.entry_price * position.quantity / max(1, position.leverage)
            self.state.cash = round(self.state.cash + margin + position.unrealized_pnl, 4)
            del self._position_book[symbol]
        self.state.positions = 0
        self.state.status = StrategyStatus.paused
        self.state.ai_message = "人工触发全面平仓并暂停"
        self.memory.append_ai("human_action", "human", "全面平仓并暂停", {"status": self.state.status.value})
        return {"status": self.state.status.value, "message": self.state.ai_message}

    async def halt(self) -> dict[str, str]:
        self._position_book.clear()
        self.state.positions = 0
        self.state.status = StrategyStatus.halted
        self.state.ai_message = "人工触发全面停止"
        self.memory.append_ai("human_action", "human", "全面停止", {"status": self.state.status.value})
        return {"status": self.state.status.value, "message": self.state.ai_message}

    async def record_command(self, operator: str, command: str) -> dict[str, object]:
        cmd = self.memory.append_command(operator=operator, command=command)
        return {"status": "ok", "message": "命令已写入AI记忆", "command": cmd}

    async def governance_payload(self) -> dict[str, object]:
        state = await self.snapshot()
        ai_usage = {
            "model_name": self._token_usage.model_name,
            "input_tokens": self._token_usage.input_tokens,
            "output_tokens": self._token_usage.output_tokens,
            "cached_tokens": self._token_usage.cached_tokens,
            "total_tokens": self._token_usage.total_tokens,
            "input_cost_usd": round(self._token_usage.input_cost_usd, 6),
            "output_cost_usd": round(self._token_usage.output_cost_usd, 6),
            "cache_cost_usd": round(self._token_usage.cache_cost_usd, 6),
            "total_cost_usd": round(self._token_usage.total_cost_usd, 6),
        }
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
                "status": state.status.value,
                "equity": state.equity,
                "cash": state.cash,
                "margin_used": state.margin_used,
                "position_value": state.position_value,
                "fees_paid": state.fees_paid,
                "realized_pnl": state.realized_pnl,
                "unrealized_pnl": state.unrealized_pnl,
                "total_return_pct": state.total_return_pct,
                "drawdown_pct": state.drawdown_pct,
                "daily_drawdown_pct": state.daily_drawdown_pct,
                "positions": state.positions,
                "ai_message": state.ai_message,
                "ai_insight": state.ai_insight,
                "last_cycle_at": state.generated_at.isoformat(),
            },
            "ai_usage": ai_usage,
            "positions": [item.model_dump(mode="json") for item in self._position_book.values()],
            "trades": [item.model_dump(mode="json") for item in list(self._trades)[:120]],
            "runtime_logs": list(self._runtime_logs)[:200],
            "ai_tasks": [item.model_dump(mode="json") for item in list(self._tasks)[:60]],
            "memory": self.memory.recent_ai(limit=80),
            "commands": self.memory.recent_commands(limit=30),
        }
