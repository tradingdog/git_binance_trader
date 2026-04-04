from __future__ import annotations

import asyncio
from typing import Any

import httpx

from git_binance_trader.config import Settings
from git_binance_trader.core.models import MarketType, SymbolSnapshot


class BinanceMarketDataService:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    async def get_top_symbols(self) -> list[SymbolSnapshot]:
        snapshots = await self._fetch_realtime_snapshots()
        if snapshots:
            return snapshots if self.settings.top_symbols_limit <= 0 else snapshots[: self.settings.top_symbols_limit]
        return []

    async def _fetch_realtime_snapshots(self) -> list[SymbolSnapshot]:
        headers = {}
        if self.settings.binance_api_key:
            headers["X-MBX-APIKEY"] = self.settings.binance_api_key

        async with httpx.AsyncClient(timeout=8.0, headers=headers) as client:
            spot_payload = await self._fetch_json_with_retry(client, "https://api.binance.com/api/v3/ticker/24hr", retries=2)
            perp_payload = await self._fetch_json_with_retry(client, "https://fapi.binance.com/fapi/v1/ticker/24hr", retries=2)

            # Alpha 接口波动较大，失败时不应影响主行情链路。
            alpha_token_payload = await self._fetch_json_with_retry(
                client,
                "https://www.binance.com/bapi/defi/v1/public/wallet-direct/buw/wallet/cex/alpha/all/token/list",
                retries=1,
            )
            alpha_info_payload = await self._fetch_json_with_retry(
                client,
                "https://www.binance.com/bapi/defi/v1/public/alpha-trade/get-exchange-info",
                retries=1,
            )

        if not isinstance(spot_payload, list) and not isinstance(perp_payload, list):
            return []

        if not isinstance(spot_payload, list):
            spot_payload = []
        if not isinstance(perp_payload, list):
            perp_payload = []
        if not isinstance(alpha_token_payload, dict):
            alpha_token_payload = {}
        if not isinstance(alpha_info_payload, dict):
            alpha_info_payload = {}

        spot_map: dict[str, dict] = {}
        for item in spot_payload:
            symbol = item.get("symbol", "")
            if not symbol.endswith("USDT"):
                continue
            price = float(item.get("lastPrice", 0.0) or 0.0)
            if price <= 0:
                continue
            spot_map[symbol] = item

        perp_map: dict[str, dict] = {}
        for item in perp_payload:
            symbol = item.get("symbol", "")
            if not symbol.endswith("USDT"):
                continue
            price = float(item.get("lastPrice", 0.0) or 0.0)
            if price <= 0:
                continue
            perp_map[symbol] = item

        alpha_snapshots = self._build_alpha_snapshots(alpha_token_payload, alpha_info_payload)

        snapshots: list[SymbolSnapshot] = []
        for symbol, item in spot_map.items():
            snapshots.append(
                SymbolSnapshot(
                    symbol=symbol,
                    price=float(item.get("lastPrice", 0.0) or 0.0),
                    market_cap_rank=0,
                    volume_24h=float(item.get("quoteVolume", 0.0) or 0.0),
                    change_pct_24h=float(item.get("priceChangePercent", 0.0) or 0.0),
                    market_type=MarketType.spot,
                    leverage=1,
                    data_source="binance-spot",
                )
            )

        for symbol, item in perp_map.items():
            snapshots.append(
                SymbolSnapshot(
                    symbol=symbol,
                    price=float(item.get("lastPrice", 0.0) or 0.0),
                    market_cap_rank=0,
                    volume_24h=float(item.get("quoteVolume", 0.0) or 0.0),
                    change_pct_24h=float(item.get("priceChangePercent", 0.0) or 0.0),
                    market_type=MarketType.perpetual,
                    leverage=self.settings.default_perpetual_leverage,
                    data_source="binance-futures",
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

    async def _fetch_json_with_retry(self, client: httpx.AsyncClient, url: str, retries: int) -> Any:
        for attempt in range(retries + 1):
            try:
                response = await client.get(url)
                response.raise_for_status()
                return response.json()
            except Exception:
                if attempt >= retries:
                    return None
                await asyncio.sleep(0.4 * (attempt + 1))

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
                    leverage=1,
                    data_source="binance-alpha",
                )
            )
        return snapshots

