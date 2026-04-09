from git_binance_trader.config import Settings
from git_binance_trader.core.exchange import SimulationExchange
from git_binance_trader.core.models import LiquidityType, MarketType, Position, Side, SymbolSnapshot, Trade
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


def test_dynamic_take_profit_expands_for_high_score_and_momentum() -> None:
    settings = Settings(initial_balance_usdt=10000.0)
    exchange = SimulationExchange(settings, RiskManager(settings))

    exchange.apply_market_prices(
        [
            SymbolSnapshot(
                symbol="SIRENUSDT",
                price=1.0,
                market_cap_rank=50,
                volume_24h=2_500_000_000,
                change_pct_24h=12.0,
                market_type=MarketType.perpetual,
                leverage=3,
                data_source="binance-futures",
                funding_rate=0.0001,
            )
        ]
    )
    exchange.submit_trade(
        Trade(
            symbol="SIRENUSDT",
            side=Side.buy,
            quantity=100,
            price=1.0,
            market_type=MarketType.perpetual,
            leverage=3,
            strategy="adaptive_opportunity_v2",
            note="机会开仓 score=9.50 risk=0.35%",
        )
    )
    high_position = exchange.positions["perpetual:SIRENUSDT"]

    exchange.submit_trade(
        Trade(
            symbol="SIRENUSDT",
            side=Side.sell,
            quantity=100,
            price=1.0,
            market_type=MarketType.perpetual,
            strategy="risk_guard",
            note="测试清仓",
        )
    )

    exchange.apply_market_prices(
        [
            SymbolSnapshot(
                symbol="SIRENUSDT",
                price=1.0,
                market_cap_rank=50,
                volume_24h=100_000_000,
                change_pct_24h=0.5,
                market_type=MarketType.perpetual,
                leverage=3,
                data_source="binance-futures",
                funding_rate=0.0005,
            )
        ]
    )
    exchange.submit_trade(
        Trade(
            symbol="SIRENUSDT",
            side=Side.buy,
            quantity=100,
            price=1.0,
            market_type=MarketType.perpetual,
            leverage=3,
            strategy="adaptive_opportunity_v2",
            note="机会开仓 score=2.20 risk=0.35%",
        )
    )
    low_position = exchange.positions["perpetual:SIRENUSDT"]

    assert high_position.take_profit_pct > low_position.take_profit_pct
    assert high_position.trailing_stop_gap_pct > 0.9
    assert low_position.take_profit_pct >= 1.2


def test_exchange_state_roundtrip_preserves_fee_accumulation() -> None:
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

    snapshot = exchange.export_state()

    restored = SimulationExchange(settings, RiskManager(settings))
    assert restored.import_state(snapshot)

    metrics = restored.account_state()
    assert metrics["fees_paid"] == 0.1575
    assert metrics["cash"] == 10009.8425


def test_exchange_remap_symbols_only_changes_alpha_market() -> None:
    settings = Settings(initial_balance_usdt=10000.0)
    exchange = SimulationExchange(settings, RiskManager(settings))

    exchange.positions = {
        "perpetual:SIREN": Position(
            symbol="SIREN",
            quantity=100,
            entry_price=1.0,
            current_price=1.0,
            market_type=MarketType.perpetual,
            side=Side.buy,
            leverage=3,
            stop_loss=0.95,
            take_profit=1.05,
            highest_price=1.0,
        ),
        "alpha:KOGEUSDT": Position(
            symbol="KOGEUSDT",
            quantity=1,
            entry_price=10.0,
            current_price=10.0,
            market_type=MarketType.alpha,
            side=Side.buy,
            leverage=1,
            stop_loss=9.0,
            take_profit=11.0,
            highest_price=10.0,
        ),
    }
    exchange.trades = [
        Trade(
            symbol="SIREN",
            side=Side.buy,
            quantity=100,
            price=1.0,
            market_type=MarketType.perpetual,
            leverage=3,
            strategy="test",
        ),
        Trade(
            symbol="KOGEUSDT",
            side=Side.buy,
            quantity=1,
            price=10.0,
            market_type=MarketType.alpha,
            strategy="test",
        ),
    ]

    changed = exchange.remap_symbols({"SIRENUSDT": "SIREN", "KOGEUSDT": "KOGE"}, market_type=MarketType.alpha)

    assert changed
    assert "perpetual:SIRENUSDT" in exchange.positions
    assert exchange.positions["perpetual:SIRENUSDT"].symbol == "SIRENUSDT"
    assert "alpha:KOGE" in exchange.positions
    assert exchange.positions["alpha:KOGE"].symbol == "KOGE"
    assert exchange.trades[0].symbol == "SIRENUSDT"
    assert exchange.trades[1].symbol == "KOGE"
