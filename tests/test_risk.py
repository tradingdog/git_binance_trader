from git_binance_trader.config import Settings
from git_binance_trader.core.risk import RiskManager


def test_risk_manager_flags_max_drawdown() -> None:
    settings = Settings(max_drawdown_pct=15.0, max_daily_drawdown_pct=5.0, max_trade_loss_pct=1.0)
    manager = RiskManager(settings)

    result = manager.evaluate(
        peak_equity=10000.0,
        current_equity=8400.0,
        start_of_day_equity=9800.0,
        single_trade_loss_pct=0.5,
    )

    assert result.breached is True
    assert result.message == "触发全程最大回撤阈值"


def test_risk_manager_allows_safe_state() -> None:
    settings = Settings(max_drawdown_pct=15.0, max_daily_drawdown_pct=5.0, max_trade_loss_pct=1.0)
    manager = RiskManager(settings)

    result = manager.evaluate(
        peak_equity=10000.0,
        current_equity=9900.0,
        start_of_day_equity=9950.0,
        single_trade_loss_pct=0.2,
    )

    assert result.breached is False
    assert result.message == "正常"
