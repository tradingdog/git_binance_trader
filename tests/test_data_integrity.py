import pytest

from git_binance_trader.config import Settings
from git_binance_trader.core.exchange import SimulationExchange
from git_binance_trader.core.models import MarketType, Side, SymbolSnapshot, Trade
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


def test_strategy_keeps_single_market_candidate_per_symbol() -> None:
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
    assert len(scored) == 1
    assert scored[0][0].symbol == "BTCUSDT"