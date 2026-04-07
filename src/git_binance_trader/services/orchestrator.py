from __future__ import annotations

import asyncio
import json
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
        self._restore_exchange_state()
        self._restore_strategy_state()
        self._sync_trade_history()
        self._lock = asyncio.Lock()
        self._last_state: DashboardState | None = None
        self._last_report = ""
        self._last_cycle_at: datetime | None = None
        self._last_report_at: datetime | None = None
        self._runner_task: asyncio.Task[None] | None = None
        self._last_watchlist_full = []
        self.logger = get_strategy_logger(self.settings.logs_dir)

    async def run_cycle(self) -> DashboardState:
        async with self._lock:
            watchlist = await self.market_data.get_top_symbols()
            self._migrate_alpha_symbols()
            self._last_watchlist_full = list(watchlist)
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
                    recent_trades=self.exchange.trades[-500:],
                    now_ts=datetime.now(timezone.utc),
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
            self._write_strategy_comparison_if_needed(state, now_ts)
            self._sync_trade_history()
            self.history_store.save_exchange_state(self.exchange.export_state())
            self.history_store.save_strategy_state(self.strategy.export_state())
            self.history_store.ensure_headroom()
            self._log_cycle(state, strategy_insight)
            return state

    async def refresh(self) -> DashboardState:
        if self._last_state is None:
            return await self.run_cycle()
        return self._last_state

    async def dashboard(self) -> dict[str, object]:
        state = await self.refresh()
        strategy_meta = self.strategy.dashboard_meta(
            watchlist=self._last_watchlist_full[:60],
            now_ts=self._last_cycle_at,
        )
        if isinstance(strategy_meta, dict):
            strategy_meta["adaptation_history"] = self._load_strategy_comparison_history(limit=12)
        return {
            "state": state,
            "message": self.exchange.last_message,
            "report": self._last_report or self.reporter.build_report(state),
            "last_cycle_at": self._last_cycle_at.isoformat() if self._last_cycle_at else None,
            "strategy_meta": strategy_meta,
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
        self.history_store.save_exchange_state(self.exchange.export_state())
        self.history_store.save_strategy_state(self.strategy.export_state())
        return {"status": self.exchange.status.value, "message": self.exchange.last_message}

    async def resume(self) -> dict[str, str]:
        self.exchange.resume()
        self.history_store.save_exchange_state(self.exchange.export_state())
        self.history_store.save_strategy_state(self.strategy.export_state())
        return {"status": self.exchange.status.value, "message": self.exchange.last_message}

    async def emergency_close(self) -> dict[str, str]:
        self.exchange.close_all_positions(reason="用户触发一键全仓平仓")
        self.exchange.pause()
        self._sync_trade_history()
        self.history_store.save_exchange_state(self.exchange.export_state())
        self.history_store.save_strategy_state(self.strategy.export_state())
        return {"status": self.exchange.status.value, "message": self.exchange.last_message}

    def _restore_exchange_state(self) -> None:
        payload = self.history_store.load_exchange_state()
        if not payload:
            return
        restored = self.exchange.import_state(payload)
        if restored:
            self.exchange.last_message = "已从持久化快照恢复交易状态"

    def _restore_strategy_state(self) -> None:
        payload = self.history_store.load_strategy_state()
        if not payload:
            return
        self.strategy.import_state(payload)

    def _sync_trade_history(self) -> None:
        persisted_count = self.history_store.trade_count()
        current_count = len(self.exchange.trades)
        if current_count <= persisted_count:
            return
        for trade in self.exchange.trades[persisted_count:]:
            self.history_store.append_trade(trade)

    def _migrate_alpha_symbols(self) -> None:
        symbol_aliases = self.market_data.alpha_symbol_aliases()
        if not symbol_aliases:
            return
        exchange_changed = self.exchange.remap_symbols(symbol_aliases)
        history_changed = self.history_store.remap_trade_symbols(symbol_aliases)
        state_changed = self.history_store.remap_exchange_state_symbols(symbol_aliases)
        if exchange_changed or history_changed or state_changed:
            self.history_store.save_exchange_state(self.exchange.export_state())

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

    def _write_strategy_comparison_if_needed(self, state: DashboardState, now_ts: datetime) -> None:
        event = self.strategy.get_and_clear_adaptation_event()
        if not event:
            return

        reports_dir = Path(self.settings.reports_dir)
        reports_dir.mkdir(parents=True, exist_ok=True)
        compare_jsonl_path = reports_dir / "strategy-compare.jsonl"
        compare_latest_path = reports_dir / "strategy-compare-latest.md"
        compare_hourly_path = reports_dir / f"strategy-compare-{now_ts.strftime('%Y%m%d-%H%M')}.md"

        payload = {
            "generated_at": now_ts.isoformat(),
            "equity": state.account.equity,
            "total_return_pct": state.account.total_return_pct,
            "fees_paid": state.account.fees_paid,
            "funding_paid": state.account.funding_paid,
            "event": event,
        }
        with compare_jsonl_path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(payload, ensure_ascii=False))
            handle.write("\n")

        before = event.get("before", {}) if isinstance(event, dict) else {}
        after = event.get("after", {}) if isinstance(event, dict) else {}
        metrics = event.get("metrics", {}) if isinstance(event, dict) else {}
        lines = [
            f"# 策略参数对比报告 {now_ts.strftime('%Y-%m-%d %H:%M UTC')}",
            "",
            "## 当前绩效快照",
            f"- 账户净值: {state.account.equity:.4f}",
            f"- 总收益率: {state.account.total_return_pct:.4f}%",
            f"- 累计手续费: {state.account.fees_paid:.4f}",
            f"- 累计资金费率支出: {state.account.funding_paid:.4f}",
            "",
            "## 本小时交易窗口",
            f"- 平仓笔数: {metrics.get('closed_trades', 0)}",
            f"- 胜率: {metrics.get('win_rate', 0.0)}",
            f"- 平均已实现盈亏: {metrics.get('avg_realized_pnl', 0.0)}",
            f"- 已实现盈亏合计: {metrics.get('realized_sum', 0.0)}",
            f"- 手续费合计: {metrics.get('fee_sum', 0.0)}",
            "",
            "## 参数变更（Before -> After）",
        ]
        for key in sorted(set(before.keys()) | set(after.keys())):
            lines.append(f"- {key}: {before.get(key)} -> {after.get(key)}")

        report = "\n".join(lines)
        compare_latest_path.write_text(report, encoding="utf-8")
        compare_hourly_path.write_text(report, encoding="utf-8")

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
        persisted = self.history_store.load_trades(limit=limit)
        source = persisted if persisted else self.exchange.trades[-limit:]
        return [trade.model_dump(mode="json") for trade in reversed(source)]

    def tail_runtime_log(self, lines: int = 500) -> str:
        lines = max(1, min(lines, 5000))
        log_path = Path(self.settings.logs_dir) / "strategy.log"
        if not log_path.exists():
            return "暂无日志"
        content = log_path.read_text(encoding="utf-8", errors="ignore").splitlines()
        return "\n".join(content[-lines:])

    def _load_strategy_comparison_history(self, limit: int = 12) -> list[dict[str, object]]:
        compare_path = Path(self.settings.reports_dir) / "strategy-compare.jsonl"
        if not compare_path.exists():
            return []
        rows: list[dict[str, object]] = []
        for raw_line in compare_path.read_text(encoding="utf-8", errors="ignore").splitlines()[-limit:]:
            if not raw_line.strip():
                continue
            try:
                payload = json.loads(raw_line)
            except json.JSONDecodeError:
                continue
            if isinstance(payload, dict):
                rows.append(payload)
        return list(reversed(rows))

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
