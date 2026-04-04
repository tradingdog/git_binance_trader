from git_binance_trader.config import Settings
from git_binance_trader.core.models import RiskStatus


class RiskManager:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    def evaluate(
        self,
        *,
        peak_equity: float,
        current_equity: float,
        start_of_day_equity: float,
        single_trade_loss_pct: float,
    ) -> RiskStatus:
        drawdown_pct = self._pct_drop(peak_equity, current_equity)
        daily_drawdown_pct = self._pct_drop(start_of_day_equity, current_equity)
        breached = False
        message = "正常"

        if drawdown_pct > self.settings.max_drawdown_pct:
            breached = True
            message = "触发全程最大回撤阈值"
        elif daily_drawdown_pct > self.settings.max_daily_drawdown_pct:
            breached = True
            message = "触发单日最大回撤阈值"
        elif single_trade_loss_pct > self.settings.max_trade_loss_pct:
            breached = True
            message = "触发单笔亏损阈值"

        return RiskStatus(
            max_drawdown_pct=round(drawdown_pct, 4),
            daily_drawdown_pct=round(daily_drawdown_pct, 4),
            single_trade_loss_pct=round(single_trade_loss_pct, 4),
            breached=breached,
            message=message,
        )

    @staticmethod
    def _pct_drop(reference: float, current: float) -> float:
        if reference <= 0:
            return 0.0
        return max(0.0, (reference - current) / reference * 100)
