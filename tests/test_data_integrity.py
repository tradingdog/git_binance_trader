from datetime import datetime, timedelta, timezone

import pytest
import httpx

from git_binance_trader.config import Settings
from git_binance_trader.core.exchange import SimulationExchange
from git_binance_trader.core.models import MarketType, Position, Side, SymbolSnapshot, Trade
from git_binance_trader.core.risk import RiskManager
from git_binance_trader.core.strategy import OpportunityStrategy
from git_binance_trader.services.binance_market_data import BinanceMarketDataService


@pytest.mark.anyio
async def test_market_data_uses_real_perp_price_without_spot_overwrite() -> None:
    service = BinanceMarketDataService(Settings())

    payloads = iter(
        [
            [{"symbol": "SIRENUSDT", "lastPrice": "83000", "quoteVolume": "1000", "priceChangePercent": "1.2"}],
            [{"symbol": "SIRENUSDT", "lastPrice": "67000", "quoteVolume": "2000", "priceChangePercent": "0.6"}],
            {"symbols": [{"symbol": "SIRENUSDT", "status": "TRADING", "quoteAsset": "USDT", "isSpotTradingAllowed": True}]},
            {"symbols": [{"symbol": "SIRENUSDT", "status": "TRADING", "quoteAsset": "USDT", "contractType": "PERPETUAL"}]},
            [{"symbol": "SIRENUSDT", "lastFundingRate": "0.0001", "nextFundingTime": 1890000000000}],
            [],
            {"code": "000000", "data": []},
            {"code": "000000", "data": {"symbols": []}},
        ]
    )

    async def fake_fetch_json_with_retry(*_, **__):
        return next(payloads)

    service._fetch_json_with_retry = fake_fetch_json_with_retry  # type: ignore[method-assign]
    snapshots = await service._fetch_realtime_snapshots()

    spot = next(item for item in snapshots if item.symbol == "SIRENUSDT" and item.market_type == MarketType.spot)
    perp = next(item for item in snapshots if item.symbol == "SIRENUSDT" and item.market_type == MarketType.perpetual)
    assert spot.price == 83000.0
    assert perp.price == 67000.0
    assert perp.data_source == "binance-futures"


@pytest.mark.anyio
async def test_market_data_rejects_non_trading_perpetual_symbols() -> None:
    service = BinanceMarketDataService(Settings())

    payloads = iter(
        [
            [],
            [
                {"symbol": "ALPACAUSDT", "lastPrice": "1", "quoteVolume": "1000", "priceChangePercent": "1.2"},
                {"symbol": "SIRENUSDT", "lastPrice": "2", "quoteVolume": "1000", "priceChangePercent": "2.2"},
            ],
            {"symbols": []},
            {
                "symbols": [
                    {"symbol": "ALPACAUSDT", "status": "SETTLING", "quoteAsset": "USDT", "contractType": "PERPETUAL"},
                    {"symbol": "SIRENUSDT", "status": "TRADING", "quoteAsset": "USDT", "contractType": "PERPETUAL"},
                ]
            },
            [
                {"symbol": "ALPACAUSDT", "lastFundingRate": "0.0001", "nextFundingTime": 1890000000000},
                {"symbol": "SIRENUSDT", "lastFundingRate": "0.0002", "nextFundingTime": 1890000000000},
            ],
            [],
            {"code": "000000", "data": []},
            {"code": "000000", "data": {"symbols": []}},
        ]
    )

    async def fake_fetch_json_with_retry(*_, **__):
        return next(payloads)

    service._fetch_json_with_retry = fake_fetch_json_with_retry  # type: ignore[method-assign]
    snapshots = await service._fetch_realtime_snapshots()
    perp_symbols = {item.symbol for item in snapshots if item.market_type == MarketType.perpetual}
    assert "ALPACAUSDT" not in perp_symbols
    assert "SIRENUSDT" in perp_symbols


@pytest.mark.anyio
async def test_market_data_excludes_large_cap_and_stablecoin_spot_perp() -> None:
    service = BinanceMarketDataService(Settings())

    payloads = iter(
        [
            [
                {"symbol": "BTCUSDT", "lastPrice": "83000", "quoteVolume": "1000", "priceChangePercent": "1.2"},
                {"symbol": "SIRENUSDT", "lastPrice": "2", "quoteVolume": "2000", "priceChangePercent": "5.2"},
                {"symbol": "USDCUSDT", "lastPrice": "1", "quoteVolume": "3000", "priceChangePercent": "0.0"},
            ],
            [
                {"symbol": "BTCUSDT", "lastPrice": "82900", "quoteVolume": "1000", "priceChangePercent": "0.8"},
                {"symbol": "SIRENUSDT", "lastPrice": "2.1", "quoteVolume": "2000", "priceChangePercent": "5.0"},
                {"symbol": "USDCUSDT", "lastPrice": "1", "quoteVolume": "4000", "priceChangePercent": "0.0"},
            ],
            {"symbols": [
                {"symbol": "BTCUSDT", "status": "TRADING", "quoteAsset": "USDT", "isSpotTradingAllowed": True},
                {"symbol": "SIRENUSDT", "status": "TRADING", "quoteAsset": "USDT", "isSpotTradingAllowed": True},
                {"symbol": "USDCUSDT", "status": "TRADING", "quoteAsset": "USDT", "isSpotTradingAllowed": True},
            ]},
            {"symbols": [
                {"symbol": "BTCUSDT", "status": "TRADING", "quoteAsset": "USDT", "contractType": "PERPETUAL"},
                {"symbol": "SIRENUSDT", "status": "TRADING", "quoteAsset": "USDT", "contractType": "PERPETUAL"},
                {"symbol": "USDCUSDT", "status": "TRADING", "quoteAsset": "USDT", "contractType": "PERPETUAL"},
            ]},
            [
                {"symbol": "BTCUSDT", "lastFundingRate": "0.0001", "nextFundingTime": 1890000000000},
                {"symbol": "SIRENUSDT", "lastFundingRate": "0.0002", "nextFundingTime": 1890000000000},
                {"symbol": "USDCUSDT", "lastFundingRate": "0.0000", "nextFundingTime": 1890000000000},
            ],
            [],
            {"code": "000000", "data": []},
            {"code": "000000", "data": {"symbols": []}},
        ]
    )

    async def fake_fetch_json_with_retry(*_, **__):
        return next(payloads)

    service._fetch_json_with_retry = fake_fetch_json_with_retry  # type: ignore[method-assign]
    snapshots = await service._fetch_realtime_snapshots()
    symbols = {(item.symbol, item.market_type) for item in snapshots}
    assert ("BTCUSDT", MarketType.spot) not in symbols
    assert ("BTCUSDT", MarketType.perpetual) not in symbols
    assert ("USDCUSDT", MarketType.spot) not in symbols
    assert ("USDCUSDT", MarketType.perpetual) not in symbols
    assert ("SIRENUSDT", MarketType.spot) in symbols
    assert ("SIRENUSDT", MarketType.perpetual) in symbols


@pytest.mark.anyio
async def test_build_alpha_snapshots_uses_searchable_symbol_and_real_market_filter() -> None:
    service = BinanceMarketDataService(Settings())

    token_payload = {
        "code": "000000",
        "data": [
            {
                "alphaId": "ALPHA_22",
                "symbol": "KOGE",
                "price": "47.99",
                "volume24h": "267221213.63",
                "percentChange24h": "0.0",
                "liquidity": "11920231.52",
            }
        ],
    }
    exchange_payload = {
        "code": "000000",
        "data": {
            "symbols": [
                {
                    "symbol": "ALPHA_22USDT",
                    "status": "TRADING",
                    "baseAsset": "ALPHA_22",
                    "quoteAsset": "USDT",
                }
            ]
        },
    }

    responses = iter(
        [
            {"code": "000000", "data": {"lastPrice": "48.00", "quoteVolume": "6667807.36", "count": 11361, "priceChangePercent": "12.01"}},
            {"code": "000000", "data": [["1","0","0","0","0","0","0","5226083.22","8504"], ["1","0","0","0","0","0","0","6603002.73","10978"], ["1","0","0","0","0","0","0","1036354.69","2132"]]},
        ]
    )

    async def fake_fetch_json_with_retry(*_, **__):
        return next(responses)

    service._fetch_json_with_retry = fake_fetch_json_with_retry  # type: ignore[method-assign]

    async with httpx.AsyncClient() as client:
        snapshots = await service._build_alpha_snapshots(client, token_payload, exchange_payload)

    assert len(snapshots) == 1
    assert snapshots[0].symbol == "KOGE"
    assert service.alpha_symbol_aliases()["KOGEUSDT"] == "KOGE"
    assert service.alpha_symbol_aliases()["ALPHA_22USDT"] == "KOGE"


def test_alpha_market_activity_filter_rejects_low_liquidity_token() -> None:
    service = BinanceMarketDataService(Settings())

    ticker_payload = {
        "code": "000000",
        "data": {"quoteVolume": "78760.96", "count": 1776},
    }
    klines_payload = {
        "code": "000000",
        "data": [
            ["1", "0", "0", "0", "0", "0", "0", "4728.91", "852"],
            ["1", "0", "0", "0", "0", "0", "0", "14986.62", "1142"],
            ["1", "0", "0", "0", "0", "0", "0", "16252.28", "1187"],
        ],
    }

    assert not service._passes_alpha_market_activity_filter(ticker_payload, klines_payload)


def test_alpha_snapshot_filter_rejects_neutral_change_range() -> None:
    service = BinanceMarketDataService(Settings())
    row = SymbolSnapshot(
        symbol="KOGE",
        price=48.0,
        market_cap_rank=1,
        volume_24h=6_000_000,
        change_pct_24h=0.0,
        market_type=MarketType.alpha,
        leverage=1,
        data_source="binance-alpha",
    )

    ticker_payload = {
        "code": "000000",
        "data": {"lastPrice": "48.00", "quoteVolume": "6667807.36", "count": 11361, "priceChangePercent": "2.50"},
    }
    klines_payload = {
        "code": "000000",
        "data": [["1", "0", "0", "0", "0", "0", "0", "5226083.22", "8504"]] * 30,
    }

    assert service._passes_alpha_market_activity_filter(ticker_payload, klines_payload)

    import asyncio
    import httpx

    async def _run() -> list[SymbolSnapshot]:
        responses = iter([ticker_payload, klines_payload])

        async def fake_fetch_json_with_retry(*_, **__):
            return next(responses)

        service._fetch_json_with_retry = fake_fetch_json_with_retry  # type: ignore[method-assign]
        async with httpx.AsyncClient() as client:
            return await service._filter_alpha_snapshots_by_market_activity(client, [row], {"KOGE": "ALPHA_22USDT"})

    filtered = asyncio.run(_run())
    assert filtered == []


def test_apply_market_prices_closes_position_on_stop_loss() -> None:
    settings = Settings(initial_balance_usdt=10000.0)
    exchange = SimulationExchange(settings, RiskManager(settings))
    exchange.submit_trade(
        Trade(
            symbol="BTCUSDT",
            side=Side.buy,
            quantity=0.01,
            price=80000,
            market_type=MarketType.spot,
            strategy="test",
        )
    )
    key = "spot:BTCUSDT"
    exchange.positions[key].stop_loss = 79000

    exchange.apply_market_prices(
        [
            SymbolSnapshot(
                symbol="BTCUSDT",
                price=78000,
                market_cap_rank=1,
                volume_24h=1_000_000,
                change_pct_24h=-3.0,
                market_type=MarketType.spot,
                leverage=1,
                data_source="binance-spot",
            )
        ]
    )

    assert key not in exchange.positions
    assert exchange.trades[-1].side == Side.sell


def test_strategy_keeps_distinct_market_candidates_per_symbol() -> None:
    strategy = OpportunityStrategy()
    watchlist = [
        SymbolSnapshot(
            symbol="BTCUSDT",
            price=83000,
            market_cap_rank=1,
            volume_24h=30_000_000_000,
            change_pct_24h=2.0,
            market_type=MarketType.spot,
            leverage=1,
            data_source="binance-spot",
        ),
        SymbolSnapshot(
            symbol="BTCUSDT",
            price=82980,
            market_cap_rank=2,
            volume_24h=25_000_000_000,
            change_pct_24h=2.2,
            market_type=MarketType.perpetual,
            leverage=3,
            data_source="binance-futures",
        ),
    ]

    scored = strategy._score_candidates(watchlist)
    assert len(scored) == 2
    assert {f"{item.market_type.value}:{item.symbol}" for item, _ in scored} == {
        "spot:BTCUSDT",
        "perpetual:BTCUSDT",
    }


def test_strategy_rotation_exit_uses_same_market_score_for_existing_position() -> None:
    strategy = OpportunityStrategy()
    strategy.params.rotation_exit_score = 1.6
    position = Position(
        symbol="SIRENUSDT",
        quantity=100,
        entry_price=1.0,
        current_price=1.0,
        market_type=MarketType.perpetual,
        side=Side.buy,
        leverage=3,
        stop_loss=0.95,
        take_profit=1.05,
        highest_price=1.0,
    )
    watchlist = [
        SymbolSnapshot(
            symbol="SIRENUSDT",
            price=1.0,
            market_cap_rank=20,
            volume_24h=1_200_000_000,
            change_pct_24h=4.0,
            market_type=MarketType.spot,
            leverage=1,
            data_source="binance-spot",
        ),
        SymbolSnapshot(
            symbol="SIRENUSDT",
            price=1.0,
            market_cap_rank=21,
            volume_24h=2_200_000_000,
            change_pct_24h=8.0,
            market_type=MarketType.perpetual,
            leverage=3,
            data_source="binance-futures",
        ),
    ]

    scored = strategy._score_candidates(watchlist)
    exits = strategy._build_rotation_exits(scored, {"perpetual:SIRENUSDT": position}, [], datetime.now(timezone.utc))

    assert exits == []


def test_strategy_respects_margin_utilization_target_for_perpetual() -> None:
    strategy = OpportunityStrategy()
    strategy.params.max_exposure_pct = 60.0
    strategy.params.target_margin_utilization_pct = 12.0
    strategy.params.position_budget_pct = 30.0
    strategy.params.entry_score_threshold = 0.1
    strategy.params.min_quote_volume = 1.0
    strategy.params.perpetual_leverage = 3

    watchlist = [
        SymbolSnapshot(
            symbol="SIRENUSDT",
            price=2.0,
            market_cap_rank=10,
            volume_24h=2_000_000_000,
            change_pct_24h=9.0,
            market_type=MarketType.perpetual,
            leverage=3,
            data_source="binance-futures",
        )
    ]

    trades, _ = strategy.decide(
        watchlist=watchlist,
        positions={},
        cash=10_000.0,
        equity=10_000.0,
        recent_trades=[],
    )

    assert len(trades) == 1
    # 目标保证金 12%，3x 永续折算后单仓名义预算不应超过 36%。
    notional = trades[0].quantity * trades[0].price
    assert notional <= 3600.0 + 1e-6


def test_strategy_adaptation_enforces_minimum_parameter_floors() -> None:
    strategy = OpportunityStrategy()
    strategy.params.max_positions = 3
    strategy.params.max_exposure_pct = 45.0
    strategy.params.target_margin_utilization_pct = 30.0
    strategy.params.position_budget_pct = 8.0

    now = datetime.now(timezone.utc)
    losing_sell = Trade(
        symbol="SIRENUSDT",
        side=Side.sell,
        quantity=1,
        price=2.0,
        realized_pnl=-5.0,
        market_type=MarketType.perpetual,
        strategy="test",
        created_at=now,
    )

    strategy._adapt_hourly([losing_sell], now)

    assert strategy.params.max_positions >= 3
    assert strategy.params.max_exposure_pct >= 45.0
    assert strategy.params.target_margin_utilization_pct >= 30.0
    assert strategy.params.position_budget_pct >= 8.0


def test_strategy_import_state_enforces_minimum_parameter_floors() -> None:
    strategy = OpportunityStrategy()
    payload = {
        "risk_per_trade_pct": 0.35,
        "params": {
            "max_positions": 2,
            "max_exposure_pct": 18.0,
            "target_margin_utilization_pct": 12.0,
            "entry_score_threshold": 2.8,
            "rotation_exit_score": 1.6,
            "position_budget_pct": 4.5,
            "min_quote_volume": 120_000_000.0,
            "perpetual_leverage": 3,
        },
        "last_adapt_hour": None,
        "last_adaptation_event": None,
        "latest_adaptation_snapshot": None,
        "first_seen_ts": {},
        "series": {},
    }

    assert strategy.import_state(payload)
    assert strategy.params.max_positions == 3
    assert strategy.params.max_exposure_pct == 45.0
    assert strategy.params.target_margin_utilization_pct == 30.0
    assert strategy.params.position_budget_pct == 8.0


def test_strategy_import_state_enforces_maximum_parameter_ceilings() -> None:
    strategy = OpportunityStrategy()
    payload = {
        "risk_per_trade_pct": 0.35,
        "params": {
            "max_positions": 10,
            "max_exposure_pct": 90.0,
            "target_margin_utilization_pct": 70.0,
            "entry_score_threshold": 2.8,
            "rotation_exit_score": 1.6,
            "position_budget_pct": 9.0,
            "min_quote_volume": 120_000_000.0,
            "perpetual_leverage": 3,
        },
        "last_adapt_hour": None,
        "last_adaptation_event": None,
        "latest_adaptation_snapshot": None,
        "first_seen_ts": {},
        "series": {},
    }

    assert strategy.import_state(payload)
    assert strategy.params.max_positions == 6
    assert strategy.params.max_exposure_pct == 60.0
    assert strategy.params.target_margin_utilization_pct == 55.0


def test_strategy_blocks_reentry_during_symbol_cooldown() -> None:
    strategy = OpportunityStrategy()
    strategy.params.entry_score_threshold = 0.5
    strategy.params.min_quote_volume = 1.0
    now = datetime.now(timezone.utc)
    watch = SymbolSnapshot(
        symbol="SIRENUSDT",
        price=2.0,
        market_cap_rank=10,
        volume_24h=2_000_000_000,
        change_pct_24h=9.0,
        market_type=MarketType.perpetual,
        leverage=3,
        data_source="binance-futures",
    )

    strategy._score_candidates = lambda watchlist, now=None: [(watch, 2.0)]  # type: ignore[method-assign]
    recent = [
        Trade(
            symbol="SIRENUSDT",
            side=Side.sell,
            quantity=1,
            price=2.1,
            market_type=MarketType.perpetual,
            strategy="risk_guard",
            note="触发止损/跟踪止盈",
            created_at=now,
        )
    ]

    trades, _ = strategy.decide(
        watchlist=[watch],
        positions={},
        cash=10_000.0,
        equity=10_000.0,
        recent_trades=recent,
        now_ts=now,
    )

    assert trades == []


def test_strategy_deweights_symbol_after_consecutive_stop_losses() -> None:
    strategy = OpportunityStrategy()
    strategy.params.entry_score_threshold = 1.0
    strategy.params.min_quote_volume = 1.0
    now = datetime.now(timezone.utc)
    watch = SymbolSnapshot(
        symbol="SIRENUSDT",
        price=2.0,
        market_cap_rank=10,
        volume_24h=2_000_000_000,
        change_pct_24h=9.0,
        market_type=MarketType.perpetual,
        leverage=3,
        data_source="binance-futures",
    )

    strategy._score_candidates = lambda watchlist, now=None: [(watch, 1.5)]  # type: ignore[method-assign]
    recent = [
        Trade(
            symbol="SIRENUSDT",
            side=Side.sell,
            quantity=1,
            price=2.1,
            market_type=MarketType.perpetual,
            strategy="risk_guard",
            note="触发止损/跟踪止盈",
            created_at=now,
        ),
        Trade(
            symbol="SIRENUSDT",
            side=Side.sell,
            quantity=1,
            price=2.0,
            market_type=MarketType.perpetual,
            strategy="risk_guard",
            note="触发止损/跟踪止盈",
            created_at=now,
        ),
    ]

    trades, _ = strategy.decide(
        watchlist=[watch],
        positions={},
        cash=10_000.0,
        equity=10_000.0,
        recent_trades=recent,
        now_ts=now + timedelta(minutes=6),
    )

    assert trades == []


def test_strategy_raises_quality_threshold_for_marginal_signals() -> None:
    strategy = OpportunityStrategy()
    strategy.params.entry_score_threshold = 1.0
    strategy.params.min_quote_volume = 1.0
    now = datetime.now(timezone.utc)
    watch = SymbolSnapshot(
        symbol="SIRENUSDT",
        price=2.0,
        market_cap_rank=10,
        volume_24h=2_000_000_000,
        change_pct_24h=9.0,
        market_type=MarketType.perpetual,
        leverage=3,
        data_source="binance-futures",
    )

    strategy._score_candidates = lambda watchlist, now=None: [(watch, 1.1)]  # type: ignore[method-assign]

    trades, _ = strategy.decide(
        watchlist=[watch],
        positions={},
        cash=10_000.0,
        equity=10_000.0,
        recent_trades=[],
        now_ts=now,
    )

    assert trades == []


def test_strategy_rotation_exit_requires_two_weak_cycles() -> None:
    strategy = OpportunityStrategy()
    strategy.params.rotation_exit_score = 1.6
    position = Position(
        symbol="SIRENUSDT",
        quantity=100,
        entry_price=1.0,
        current_price=1.0,
        market_type=MarketType.perpetual,
        side=Side.buy,
        leverage=3,
        stop_loss=0.95,
        take_profit=1.05,
        highest_price=1.0,
    )
    watch = SymbolSnapshot(
        symbol="SIRENUSDT",
        price=1.0,
        market_cap_rank=20,
        volume_24h=1_200_000_000,
        change_pct_24h=1.0,
        market_type=MarketType.perpetual,
        leverage=3,
        data_source="binance-futures",
    )
    now = datetime.now(timezone.utc)

    scored = [(watch, 1.2)]
    exits_first = strategy._build_rotation_exits(
        scored,
        {"perpetual:SIRENUSDT": position},
        [
            Trade(
                symbol="SIRENUSDT",
                side=Side.buy,
                quantity=100,
                price=1.0,
                market_type=MarketType.perpetual,
                strategy="test",
                created_at=now - timedelta(minutes=8),
            )
        ],
        now,
    )
    exits_second = strategy._build_rotation_exits(
        scored,
        {"perpetual:SIRENUSDT": position},
        [
            Trade(
                symbol="SIRENUSDT",
                side=Side.buy,
                quantity=100,
                price=1.0,
                market_type=MarketType.perpetual,
                strategy="test",
                created_at=now - timedelta(minutes=8),
            )
        ],
        now,
    )

    assert exits_first == []
    assert len(exits_second) == 1


def test_strategy_rotation_exit_respects_min_hold_time() -> None:
    strategy = OpportunityStrategy()
    strategy.params.rotation_exit_score = 1.6
    position = Position(
        symbol="SIRENUSDT",
        quantity=100,
        entry_price=1.0,
        current_price=1.0,
        market_type=MarketType.perpetual,
        side=Side.buy,
        leverage=3,
        stop_loss=0.95,
        take_profit=1.05,
        highest_price=1.0,
    )
    watch = SymbolSnapshot(
        symbol="SIRENUSDT",
        price=1.0,
        market_cap_rank=20,
        volume_24h=1_200_000_000,
        change_pct_24h=1.0,
        market_type=MarketType.perpetual,
        leverage=3,
        data_source="binance-futures",
    )
    now = datetime.now(timezone.utc)
    scored = [(watch, 1.2)]

    exits = strategy._build_rotation_exits(
        scored,
        {"perpetual:SIRENUSDT": position},
        [
            Trade(
                symbol="SIRENUSDT",
                side=Side.buy,
                quantity=100,
                price=1.0,
                market_type=MarketType.perpetual,
                strategy="test",
                created_at=now - timedelta(minutes=3),
            )
        ],
        now,
    )

    assert exits == []


def test_strategy_blocks_reentry_after_rotation_exit() -> None:
    strategy = OpportunityStrategy()
    strategy.params.entry_score_threshold = 0.5
    strategy.params.min_quote_volume = 1.0
    now = datetime.now(timezone.utc)
    watch = SymbolSnapshot(
        symbol="SIRENUSDT",
        price=2.0,
        market_cap_rank=10,
        volume_24h=2_000_000_000,
        change_pct_24h=9.0,
        market_type=MarketType.perpetual,
        leverage=3,
        data_source="binance-futures",
    )

    strategy._score_candidates = lambda watchlist, now=None: [(watch, 2.5)]  # type: ignore[method-assign]
    recent = [
        Trade(
            symbol="SIRENUSDT",
            side=Side.sell,
            quantity=1,
            price=2.1,
            market_type=MarketType.perpetual,
            strategy="test",
            note="机会衰减退出",
            created_at=now - timedelta(minutes=10),
        )
    ]

    trades, _ = strategy.decide(
        watchlist=[watch],
        positions={},
        cash=10_000.0,
        equity=10_000.0,
        recent_trades=recent,
        now_ts=now,
    )

    assert trades == []


def test_strategy_blocks_high_frequency_symbol_trading() -> None:
    strategy = OpportunityStrategy()
    strategy.params.entry_score_threshold = 0.5
    strategy.params.min_quote_volume = 1.0
    now = datetime.now(timezone.utc)
    watch = SymbolSnapshot(
        symbol="SIRENUSDT",
        price=2.0,
        market_cap_rank=10,
        volume_24h=2_000_000_000,
        change_pct_24h=9.0,
        market_type=MarketType.perpetual,
        leverage=3,
        data_source="binance-futures",
    )

    strategy._score_candidates = lambda watchlist, now=None: [(watch, 2.5)]  # type: ignore[method-assign]
    recent = [
        Trade(
            symbol="SIRENUSDT",
            side=Side.sell if idx % 2 else Side.buy,
            quantity=1,
            price=2.0,
            market_type=MarketType.perpetual,
            strategy="test",
            created_at=now - timedelta(minutes=5),
        )
        for idx in range(14)
    ]

    trades, _ = strategy.decide(
        watchlist=[watch],
        positions={},
        cash=10_000.0,
        equity=10_000.0,
        recent_trades=recent,
        now_ts=now,
    )

    assert trades == []