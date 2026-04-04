from __future__ import annotations

from random import Random
import httpx

from git_binance_trader.config import Settings
from git_binance_trader.core.models import MarketType, SymbolSnapshot


class BinanceMarketDataService:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self._random = Random(42)
        self._seed = [
            ("BTCUSDT", 83500.0, 1, 52000000000.0, 1.7, MarketType.spot),
            ("ETHUSDT", 1820.0, 2, 27000000000.0, 2.1, MarketType.spot),
            ("SOLUSDT", 126.5, 6, 8500000000.0, 4.3, MarketType.perpetual),
            ("BNBUSDT", 602.1, 5, 2100000000.0, -0.4, MarketType.spot),
            ("DOGEUSDT", 0.19, 10, 1450000000.0, 6.9, MarketType.alpha),
        ]

    async def get_top_symbols(self) -> list[SymbolSnapshot]:
        snapshots = await self._fetch_public_tickers()
        if snapshots:
            return snapshots[: self.settings.top_symbols_limit]
        return self._fallback_watchlist()

    async def _fetch_public_tickers(self) -> list[SymbolSnapshot]:
        url = "https://api.binance.com/api/v3/ticker/24hr"
        try:
            async with httpx.AsyncClient(timeout=3.0) as client:
                response = await client.get(url)
                response.raise_for_status()
                payload = response.json()
        except Exception:
            return []

        snapshots: list[SymbolSnapshot] = []
        rank = 1
        for item in payload:
            symbol = item.get("symbol", "")
            if not symbol.endswith("USDT"):
                continue
            snapshots.append(
                SymbolSnapshot(
                    symbol=symbol,
                    price=float(item.get("lastPrice", 0.0) or 0.0),
                    market_cap_rank=rank,
                    volume_24h=float(item.get("quoteVolume", 0.0) or 0.0),
                    change_pct_24h=float(item.get("priceChangePercent", 0.0) or 0.0),
                    market_type=MarketType.spot,
                )
            )
            rank += 1
            if rank > self.settings.top_symbols_limit:
                break
        return snapshots

    def _fallback_watchlist(self) -> list[SymbolSnapshot]:
        watchlist: list[SymbolSnapshot] = []
        for symbol, price, rank, volume, change, market_type in self._seed:
            drift = self._random.uniform(-0.01, 0.01)
            watchlist.append(
                SymbolSnapshot(
                    symbol=symbol,
                    price=round(price * (1 + drift), 4),
                    market_cap_rank=rank,
                    volume_24h=volume,
                    change_pct_24h=round(change + self._random.uniform(-1.5, 1.5), 2),
                    market_type=market_type,
                )
            )
        return watchlist
