from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from pathlib import Path

from git_binance_trader.config import get_settings
from git_binance_trader.core.exchange import SimulationExchange
from git_binance_trader.core.models import AccountSnapshot, DashboardState
from git_binance_trader.core.risk import RiskManager
from git_binance_trader.core.strategy import OpportunityStrategy
from git_binance_trader.services.binance_market_data import BinanceMarketDataService
from git_binance_trader.services.reporter import DailyReporter


class TradingOrchestrator:
    def __init__(self) -> None:
        self.settings = get_settings()
        self.risk_manager = RiskManager(self.settings)
        self.exchange = SimulationExchange(self.settings, self.risk_manager)
        self.market_data = BinanceMarketDataService(self.settings)
        self.strategy = OpportunityStrategy()
        self.reporter = DailyReporter()
        self._lock = asyncio.Lock()
        self._last_state: DashboardState | None = None
        self._last_report = ""
        self._last_cycle_at: datetime | None = None
        self._report_date = ""
        self._runner_task: asyncio.Task[None] | None = None

    async def run_cycle(self) -> DashboardState:
        async with self._lock:
            watchlist = await self.market_data.get_top_symbols()
            self.exchange.apply_market_prices(watchlist)
            strategy_insight = "等待信号"
            if self.exchange.status.value == "running":
                pre_metrics = self.exchange.account_state()
                equity = pre_metrics["equity"]
                planned_trades, strategy_insight = self.strategy.decide(
                    watchlist=watchlist,
                    positions=self.exchange.positions,
                    cash=self.exchange.cash,
                    equity=equity,
                )
                for trade in planned_trades:
                    if trade.symbol not in self.exchange.positions or trade.side.value == "sell":
                        self.exchange.submit_trade(trade)
                self.exchange.apply_market_prices(watchlist)

            breached, message, metrics = self.exchange.evaluate_risk()
            risk_status = self.risk_manager.evaluate(
                peak_equity=self.exchange.peak_equity,
                current_equity=metrics["equity"],
                start_of_day_equity=self.exchange.start_of_day_equity,
                single_trade_loss_pct=metrics["single_trade_loss_pct"],
            )
            if breached:
                self.exchange.last_message = message

            account = AccountSnapshot(
                equity=metrics["equity"],
                cash=metrics["cash"],
                unrealized_pnl=metrics["unrealized_pnl"],
                realized_pnl=metrics["realized_pnl"],
                total_return_pct=metrics["total_return_pct"],
                drawdown_pct=metrics["drawdown_pct"],
                daily_drawdown_pct=metrics["daily_drawdown_pct"],
                status=self.exchange.status,
                risk_status=risk_status,
            )
            state = DashboardState(
                account=account,
                positions=list(self.exchange.positions.values()),
                trades=list(reversed(self.exchange.trades[-10:])),
                watchlist=watchlist[:10],
                strategy_insight=strategy_insight,
            )
            self._last_state = state
            self._last_report = self.reporter.build_report(state)
            self._last_cycle_at = datetime.now(timezone.utc)
            self._write_daily_report_if_needed(self._last_report)
            return state

    async def refresh(self) -> DashboardState:
        if self._last_state is None:
            return await self.run_cycle()
        return self._last_state

    async def dashboard(self) -> dict[str, object]:
        state = await self.refresh()
        return {
            "state": state,
            "message": self.exchange.last_message,
            "report": self._last_report or self.reporter.build_report(state),
            "last_cycle_at": self._last_cycle_at.isoformat() if self._last_cycle_at else None,
        }

    async def start(self) -> None:
        if self._runner_task is None or self._runner_task.done():
            self._runner_task = asyncio.create_task(self._run_forever())

    async def stop(self) -> None:
        if self._runner_task is not None:
            self._runner_task.cancel()
            try:
                await self._runner_task
            except asyncio.CancelledError:
                pass
            self._runner_task = None

    async def pause(self) -> dict[str, str]:
        self.exchange.pause()
        return {"status": self.exchange.status.value, "message": self.exchange.last_message}

    async def resume(self) -> dict[str, str]:
        self.exchange.resume()
        return {"status": self.exchange.status.value, "message": self.exchange.last_message}

    async def emergency_close(self) -> dict[str, str]:
        self.exchange.close_all_positions(reason="用户触发一键全仓平仓")
        self.exchange.pause()
        return {"status": self.exchange.status.value, "message": self.exchange.last_message}

    async def _run_forever(self) -> None:
        while True:
            try:
                await self.run_cycle()
            except Exception as exc:
                self.exchange.last_message = f"后台循环异常: {exc}"
            await asyncio.sleep(self.settings.cycle_interval_seconds)

    def _write_daily_report_if_needed(self, report: str) -> None:
        report_date = datetime.now().strftime("%Y-%m-%d")
        reports_dir = Path(self.settings.reports_dir)
        reports_dir.mkdir(parents=True, exist_ok=True)
        report_path = reports_dir / f"report-{report_date}.md"
        report_path.write_text(report, encoding="utf-8")
        self._report_date = report_date


orchestrator = TradingOrchestrator()
