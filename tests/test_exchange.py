from git_binance_trader.config import Settings
from git_binance_trader.core.exchange import SimulationExchange
from git_binance_trader.core.models import LiquidityType, MarketType, Side, Trade
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
    assert metrics["cash"] == 10009.8425
    assert metrics["realized_pnl"] == 9.8425
    assert metrics["fees_paid"] == 0.1575
    assert metrics["equity"] == 10009.8425


def test_exchange_perpetual_trade_accounts_for_open_and_close_fees() -> None:
    settings = Settings(
        initial_balance_usdt=10000.0,
        perpetual_maker_fee_rate=0.00018,
        perpetual_taker_fee_rate=0.00045,
    )
    exchange = SimulationExchange(settings, RiskManager(settings))

    exchange.submit_trade(
        Trade(
            symbol="ETHUSDT",
            side=Side.buy,
            quantity=2,
            price=100,
            market_type=MarketType.perpetual,
            leverage=2,
            strategy="test",
        )
    )
    exchange.submit_trade(
        Trade(
            symbol="ETHUSDT",
            side=Side.sell,
            quantity=2,
            price=110,
            market_type=MarketType.perpetual,
            strategy="test",
        )
    )

    metrics = exchange.account_state()
    assert metrics["realized_pnl"] == 19.9244
    assert metrics["fees_paid"] == 0.0756
    assert metrics["cash"] == 10019.9244


def test_exchange_uses_taker_fee_for_risk_guard_auto_orders() -> None:
    settings = Settings(
        initial_balance_usdt=10000.0,
        spot_maker_fee_rate=0.001,
        spot_taker_fee_rate=0.002,
    )
    exchange = SimulationExchange(settings, RiskManager(settings))

    exchange.submit_trade(
        Trade(
            symbol="BTCUSDT",
            side=Side.buy,
            quantity=1,
            price=100,
            market_type=MarketType.spot,
            strategy="adaptive_opportunity_v1",
        )
    )
    exchange.submit_trade(
        Trade(
            symbol="BTCUSDT",
            side=Side.sell,
            quantity=1,
            price=110,
            market_type=MarketType.spot,
            strategy="risk_guard",
        )
    )

    metrics = exchange.account_state()
    assert metrics["realized_pnl"] == 9.68
    assert metrics["fees_paid"] == 0.32
    assert metrics["cash"] == 10009.68


def test_exchange_alpha_uses_spot_maker_taker_fee_rates() -> None:
    settings = Settings(
        initial_balance_usdt=10000.0,
        spot_maker_fee_rate=0.001,
        spot_taker_fee_rate=0.0015,
        perpetual_maker_fee_rate=0.0001,
        perpetual_taker_fee_rate=0.0002,
    )
    exchange = SimulationExchange(settings, RiskManager(settings))

    exchange.submit_trade(
        Trade(
            symbol="ALPHAUSDT",
            side=Side.buy,
            quantity=1,
            price=100,
            market_type=MarketType.alpha,
            liquidity_type=LiquidityType.maker,
            strategy="adaptive_opportunity_v1",
        )
    )
    exchange.submit_trade(
        Trade(
            symbol="ALPHAUSDT",
            side=Side.sell,
            quantity=1,
            price=110,
            market_type=MarketType.alpha,
            liquidity_type=LiquidityType.taker,
            strategy="adaptive_opportunity_v1",
        )
    )

    metrics = exchange.account_state()
    assert metrics["realized_pnl"] == 9.735
    assert metrics["fees_paid"] == 0.265
    assert metrics["cash"] == 10009.735
