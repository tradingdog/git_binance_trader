from git_binance_trader.config import Settings
from git_binance_trader.core.exchange import SimulationExchange
from git_binance_trader.core.models import MarketType, Side, Trade
from git_binance_trader.core.risk import RiskManager


def test_exchange_realizes_pnl_without_double_counting_cash() -> None:
    settings = Settings(initial_balance_usdt=10000.0)
    exchange = SimulationExchange(settings, RiskManager(settings))

    exchange.submit_trade(
        Trade(
            symbol="BTCUSDT",
            side=Side.buy,
            quantity=1,
            price=100,
            market_type=MarketType.spot,
            strategy="test",
        )
    )
    exchange.submit_trade(
        Trade(
            symbol="BTCUSDT",
            side=Side.sell,
            quantity=1,
            price=110,
            market_type=MarketType.spot,
            strategy="test",
        )
    )

    metrics = exchange.account_state()
    assert metrics["cash"] == 10010.0
    assert metrics["realized_pnl"] == 10.0
    assert metrics["equity"] == 10010.0
