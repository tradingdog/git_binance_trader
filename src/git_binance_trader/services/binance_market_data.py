from __future__ import annotations

import asyncio
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
        snapshots = await self._fetch_realtime_snapshots()
        if snapshots:
            return snapshots if self.settings.top_symbols_limit <= 0 else snapshots[: self.settings.top_symbols_limit]
        return self._fallback_watchlist()

    async def _fetch_realtime_snapshots(self) -> list[SymbolSnapshot]:
        headers = {}
        if self.settings.binance_api_key:
            headers["X-MBX-APIKEY"] = self.settings.binance_api_key

        try:
            async with httpx.AsyncClient(timeout=4.0, headers=headers) as client:
                spot_resp, perp_resp, alpha_token_resp, alpha_info_resp = await self._fetch_bundle(client)
        except Exception:
            return []

        spot_payload = spot_resp.json() if spot_resp else []
        perp_payload = perp_resp.json() if perp_resp else []
        alpha_token_payload = alpha_token_resp.json() if alpha_token_resp else {}
        alpha_info_payload = alpha_info_resp.json() if alpha_info_resp else {}

        perp_map: dict[str, dict] = {}
        for item in perp_payload:
            symbol = item.get("symbol", "")
            if symbol.endswith("USDT"):
                perp_map[symbol] = item

        alpha_snapshots = self._build_alpha_snapshots(alpha_token_payload, alpha_info_payload)

        snapshots: list[SymbolSnapshot] = []
        for item in spot_payload:
            symbol = item.get("symbol", "")
            if not symbol.endswith("USDT"):
                continue
            if float(item.get("lastPrice", 0.0) or 0.0) <= 0:
                continue

            market_type = MarketType.spot
            if symbol in perp_map:
                market_type = MarketType.perpetual

            snapshots.append(
                SymbolSnapshot(
                    symbol=symbol,
                    price=float(item.get("lastPrice", 0.0) or 0.0),
                    market_cap_rank=0,
                    volume_24h=float(item.get("quoteVolume", 0.0) or 0.0),
                    change_pct_24h=float(item.get("priceChangePercent", 0.0) or 0.0),
                    market_type=market_type,
                )
            )

        merged = snapshots + alpha_snapshots
        ordered = sorted(
            merged,
            key=lambda row: (1 if row.market_type == MarketType.alpha else 0, row.volume_24h),
            reverse=True,
        )
        for idx, row in enumerate(ordered, start=1):
            row.market_cap_rank = idx
        return ordered

    async def _fetch_bundle(self, client: httpx.AsyncClient):
        spot_url = "https://api.binance.com/api/v3/ticker/24hr"
        perp_url = "https://fapi.binance.com/fapi/v1/ticker/24hr"
        alpha_token_url = "https://www.binance.com/bapi/defi/v1/public/wallet-direct/buw/wallet/cex/alpha/all/token/list"
        alpha_info_url = "https://www.binance.com/bapi/defi/v1/public/alpha-trade/get-exchange-info"
        spot_resp, perp_resp, alpha_token_resp, alpha_info_resp = await asyncio.gather(
            client.get(spot_url),
            client.get(perp_url),
            client.get(alpha_token_url),
            client.get(alpha_info_url),
        )
        spot_resp.raise_for_status()
        perp_resp.raise_for_status()
        alpha_token_resp.raise_for_status()
        alpha_info_resp.raise_for_status()
        return spot_resp, perp_resp, alpha_token_resp, alpha_info_resp

    def _build_alpha_snapshots(self, alpha_token_payload: dict, alpha_info_payload: dict) -> list[SymbolSnapshot]:
        if alpha_token_payload.get("code") != "000000" or alpha_info_payload.get("code") != "000000":
            return []

        token_by_alpha_id: dict[str, dict] = {}
        for item in alpha_token_payload.get("data", []) or []:
            alpha_id = str(item.get("alphaId", "")).upper()
            if alpha_id:
                token_by_alpha_id[alpha_id] = item

        snapshots: list[SymbolSnapshot] = []
        for symbol_info in alpha_info_payload.get("data", {}).get("symbols", []) or []:
            if symbol_info.get("status") != "TRADING":
                continue
            base_asset = str(symbol_info.get("baseAsset", "")).upper()
            quote_asset = str(symbol_info.get("quoteAsset", "")).upper()
            token_item = token_by_alpha_id.get(base_asset)
            if not token_item or quote_asset != "USDT":
                continue

            display_symbol = f"{str(token_item.get('symbol', '')).upper()}USDT"
            price = float(token_item.get("price", 0.0) or 0.0)
            if not display_symbol or price <= 0:
                continue

            snapshots.append(
                SymbolSnapshot(
                    symbol=display_symbol,
                    price=price,
                    market_cap_rank=0,
                    volume_24h=float(token_item.get("volume24h", 0.0) or 0.0),
                    change_pct_24h=float(token_item.get("percentChange24h", 0.0) or 0.0),
                    market_type=MarketType.alpha,
                )
            )
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
