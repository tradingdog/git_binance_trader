from __future__ import annotations

from datetime import datetime, timezone
from git_binance_trader.core.models import DashboardState


class DailyReporter:
    def build_report(self, state: DashboardState, now: datetime | None = None) -> str:
        now_ts = now or datetime.now(timezone.utc)
        lines = [
            f"# 每小时策略报告 {now_ts.strftime('%Y-%m-%d %H:00 UTC')}",
            "",
            f"- 账户净值: {state.account.equity:.2f} USDT",
            f"- 总收益率: {state.account.total_return_pct:.2f}%",
            f"- 累计手续费: {state.account.fees_paid:.4f} USDT",
            f"- 全程回撤: {state.account.drawdown_pct:.2f}%",
            f"- 单日回撤: {state.account.daily_drawdown_pct:.2f}%",
            f"- 风险状态: {state.account.risk_status.message}",
            f"- 策略洞察: {state.strategy_insight or '暂无'}",
            f"- 生成时间: {now_ts.isoformat()}",
            "",
            "## 持仓",
        ]
        if not state.positions:
            lines.append("- 当前无持仓")
        for position in state.positions:
            lines.append(
                f"- {position.symbol}: 数量 {position.quantity}, 浮盈亏 {position.unrealized_pnl:.2f}"
            )
        lines.append("")
        lines.append("## 最新成交")
        if not state.trades:
            lines.append("- 暂无成交")
        for trade in state.trades[:5]:
            lines.append(
                f"- {trade.symbol} {trade.side.value} {trade.quantity} @ {trade.price} ({trade.note})"
            )
        return "\n".join(lines)
