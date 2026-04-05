from __future__ import annotations

import asyncio
from datetime import datetime, timedelta, timezone
from pathlib import Path

from git_binance_trader.config import get_settings
from git_binance_trader.core.exchange import SimulationExchange
from git_binance_trader.core.models import AccountSnapshot, DashboardState, EquityPoint
from git_binance_trader.core.risk import RiskManager
from git_binance_trader.core.strategy import OpportunityStrategy
from git_binance_trader.services.binance_market_data import BinanceMarketDataService
from git_binance_trader.services.history import EquityHistoryStore
from git_binance_trader.services.logging_setup import get_strategy_logger
from git_binance_trader.services.reporter import DailyReporter


class TradingOrchestrator:
    def __init__(self) -> None:
        self.settings = get_settings()
        self.risk_manager = RiskManager(self.settings)
        self.exchange = SimulationExchange(self.settings, self.risk_manager)
        self.market_data = BinanceMarketDataService(self.settings)
        self.strategy = OpportunityStrategy()
        self.reporter = DailyReporter()
        self.history_store = EquityHistoryStore(self.settings)
        self._lock = asyncio.Lock()
        self._last_state: DashboardState | None = None
        self._last_report = ""
        self._last_cycle_at: datetime | None = None
        self._last_report_at: datetime | None = None
        self._runner_task: asyncio.Task[None] | None = None
        self.logger = get_strategy_logger(self.settings.logs_dir)

    async def run_cycle(self) -> DashboardState:
        async with self._lock:
            watchlist = await self.market_data.get_top_symbols()
            if not watchlist:
                self.exchange.last_message = "行情API拉取失败，已跳过本轮交易"
            self.exchange.apply_market_prices(watchlist)
            strategy_insight = "等待信号"
            if not watchlist:
                strategy_insight = "实时行情缺失，策略未执行"
            elif self.exchange.status.value == "running":
                pre_metrics = self.exchange.account_state()
                equity = pre_metrics["equity"]
                planned_trades, strategy_insight = self.strategy.decide(
                    watchlist=watchlist,
                    positions=self.exchange.positions,
                    cash=self.exchange.cash,
                    equity=equity,
                )
                for trade in planned_trades:
                    has_position = any(
                        position.symbol == trade.symbol and position.market_type == trade.market_type
                        for position in self.exchange.positions.values()
                    )
                    if trade.side.value == "sell" or not has_position:
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
                margin_used=metrics["margin_used"],
                position_value=metrics["position_value"],
                balance_check_delta=metrics["balance_check_delta"],
                unrealized_pnl=metrics["unrealized_pnl"],
                realized_pnl=metrics["realized_pnl"],
                fees_paid=metrics["fees_paid"],
                funding_paid=metrics["funding_paid"],
                total_return_pct=metrics["total_return_pct"],
                drawdown_pct=metrics["drawdown_pct"],
                daily_drawdown_pct=metrics["daily_drawdown_pct"],
                status=self.exchange.status,
                risk_status=risk_status,
            )
            now_ts = datetime.now(timezone.utc)
            self.history_store.append(
                EquityPoint(
                    timestamp=now_ts,
                    equity=metrics["equity"],
                    cash=metrics["cash"],
                    margin_used=metrics["margin_used"],
                    position_value=metrics["position_value"],
                )
            )
            state = DashboardState(
                account=account,
                positions=list(self.exchange.positions.values()),
                trades=list(reversed(self.exchange.trades[-10:])),
                watchlist=watchlist[:10],
                equity_history=self.history_store.load(since=now_ts - timedelta(days=7)),
                storage=self.history_store.storage_status(),
                strategy_insight=strategy_insight,
                generated_at=now_ts,
            )
            self._last_state = state
            self._last_report = self.reporter.build_report(state, now=now_ts)
            self._last_cycle_at = now_ts
            self._write_report_snapshot(self._last_report)
            self._write_hourly_report_if_due(self._last_report, now_ts)
            self.history_store.ensure_headroom()
            self._log_cycle(state, strategy_insight)
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
                self.logger.exception("cycle_error=%s", exc)
            await asyncio.sleep(self.settings.cycle_interval_seconds)

    def _write_report_snapshot(self, report: str) -> None:
        reports_dir = Path(self.settings.reports_dir)
        reports_dir.mkdir(parents=True, exist_ok=True)
        latest_path = reports_dir / "latest.md"
        latest_path.write_text(report, encoding="utf-8")

    def _write_hourly_report_if_due(self, report: str, now_ts: datetime) -> None:
        if self._last_report_at and now_ts - self._last_report_at < timedelta(minutes=self.settings.report_interval_minutes):
            return
        reports_dir = Path(self.settings.reports_dir)
        reports_dir.mkdir(parents=True, exist_ok=True)
        hourly_path = reports_dir / f"report-{now_ts.strftime('%Y%m%d-%H00')}.md"
        hourly_path.write_text(report, encoding="utf-8")
        self._last_report_at = now_ts

    def list_report_files(self) -> list[str]:
        reports_dir = Path(self.settings.reports_dir)
        if not reports_dir.exists():
            return []
        return sorted((path.name for path in reports_dir.glob("report-*.md")), reverse=True)

    def latest_report_text(self) -> str:
        reports_dir = Path(self.settings.reports_dir)
        latest_path = reports_dir / "latest.md"
        if latest_path.exists():
            return latest_path.read_text(encoding="utf-8")
        return self._last_report or "暂无报告"

    def list_recent_trades(self, limit: int = 500) -> list[dict[str, object]]:
        limit = max(1, min(limit, 5000))
        return [trade.model_dump(mode="json") for trade in reversed(self.exchange.trades[-limit:])]

    def tail_runtime_log(self, lines: int = 500) -> str:
        lines = max(1, min(lines, 5000))
        log_path = Path(self.settings.logs_dir) / "strategy.log"
        if not log_path.exists():
            return "暂无日志"
        content = log_path.read_text(encoding="utf-8", errors="ignore").splitlines()
        return "\n".join(content[-lines:])

    def _log_cycle(self, state: DashboardState, strategy_insight: str) -> None:
        self.logger.info(
            "cycle status=%s equity=%.4f cash=%.4f return=%.4f drawdown=%.4f positions=%d trades=%d insight=%s",
            state.account.status.value,
            state.account.equity,
            state.account.cash,
            state.account.total_return_pct,
            state.account.drawdown_pct,
            len(state.positions),
            len(state.trades),
            strategy_insight,
        )


orchestrator = TradingOrchestrator()
