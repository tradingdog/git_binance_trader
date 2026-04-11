from __future__ import annotations

import asyncio
from typing import Any

import httpx

from git_binance_trader.config import Settings
from git_binance_trader.core.models import MarketType, SymbolSnapshot


class BinanceMarketDataService:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self._latest_alpha_symbol_aliases: dict[str, str] = {}
        self._latest_alpha_actual_symbols: dict[str, str] = {}

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
            spot_exchange_info_payload = await self._fetch_json_with_retry(client, "https://api.binance.com/api/v3/exchangeInfo", retries=2)
            perp_exchange_info_payload = await self._fetch_json_with_retry(client, "https://fapi.binance.com/fapi/v1/exchangeInfo", retries=2)
            premium_payload = await self._fetch_json_with_retry(client, "https://fapi.binance.com/fapi/v1/premiumIndex", retries=2)
            funding_info_payload = await self._fetch_json_with_retry(client, "https://fapi.binance.com/fapi/v1/fundingInfo", retries=1)

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

            alpha_snapshots = await self._build_alpha_snapshots(client, alpha_token_payload, alpha_info_payload)

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
        if not isinstance(spot_exchange_info_payload, dict):
            spot_exchange_info_payload = {}
        if not isinstance(perp_exchange_info_payload, dict):
            perp_exchange_info_payload = {}
        if not isinstance(premium_payload, list):
            premium_payload = []
        if not isinstance(funding_info_payload, list):
            funding_info_payload = []

        # 关键风控：仅允许 Binance 官方 exchangeInfo 标记为 TRADING 的交易对进入策略池。
        spot_trading_symbols = self._extract_spot_trading_symbols(spot_exchange_info_payload)
        perp_trading_symbols = self._extract_perpetual_trading_symbols(perp_exchange_info_payload)

        spot_map: dict[str, dict] = {}
        for item in spot_payload:
            symbol = item.get("symbol", "")
            if symbol not in spot_trading_symbols:
                continue
            if not symbol.endswith("USDT"):
                continue
            if self._should_exclude_symbol(symbol, MarketType.spot):
                continue
            price = float(item.get("lastPrice", 0.0) or 0.0)
            if price <= 0:
                continue
            spot_map[symbol] = item

        perp_map: dict[str, dict] = {}
        for item in perp_payload:
            symbol = item.get("symbol", "")
            if symbol not in perp_trading_symbols:
                continue
            if not symbol.endswith("USDT"):
                continue
            if self._should_exclude_symbol(symbol, MarketType.perpetual):
                continue
            price = float(item.get("lastPrice", 0.0) or 0.0)
            if price <= 0:
                continue
            perp_map[symbol] = item

        premium_map: dict[str, dict] = {}
        for item in premium_payload:
            symbol = str(item.get("symbol", ""))
            if symbol:
                premium_map[symbol] = item

        # fundingInfo 仅返回有调整的交易对，未返回的默认按 8 小时间隔。
        funding_interval_map: dict[str, int] = {}
        for item in funding_info_payload:
            symbol = str(item.get("symbol", ""))
            if not symbol:
                continue
            interval_hours = int(item.get("fundingIntervalHours", 8) or 8)
            funding_interval_map[symbol] = max(interval_hours, 1)

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
            premium_item = premium_map.get(symbol, {})
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
                    funding_rate=float(premium_item.get("lastFundingRate", 0.0) or 0.0),
                    next_funding_time_ms=int(premium_item.get("nextFundingTime", 0) or 0),
                    funding_interval_hours=funding_interval_map.get(symbol, 8),
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

    def alpha_symbol_aliases(self) -> dict[str, str]:
        return dict(self._latest_alpha_symbol_aliases)

    def alpha_actual_symbols(self) -> dict[str, str]:
        return dict(self._latest_alpha_actual_symbols)

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

    async def _build_alpha_snapshots(
        self,
        client: httpx.AsyncClient,
        alpha_token_payload: dict,
        alpha_info_payload: dict,
    ) -> list[SymbolSnapshot]:
        if alpha_token_payload.get("code") != "000000" or alpha_info_payload.get("code") != "000000":
            self._latest_alpha_symbol_aliases = {}
            self._latest_alpha_actual_symbols = {}
            return []

        token_by_alpha_id: dict[str, dict] = {}
        for item in alpha_token_payload.get("data", []) or []:
            alpha_id = str(item.get("alphaId", "")).upper()
            if alpha_id:
                token_by_alpha_id[alpha_id] = item

        snapshots: list[SymbolSnapshot] = []
        alias_map: dict[str, str] = {}
        actual_symbol_map: dict[str, str] = {}
        for symbol_info in alpha_info_payload.get("data", {}).get("symbols", []) or []:
            if symbol_info.get("status") != "TRADING":
                continue
            base_asset = str(symbol_info.get("baseAsset", "")).upper()
            quote_asset = str(symbol_info.get("quoteAsset", "")).upper()
            token_item = token_by_alpha_id.get(base_asset)
            if not token_item or quote_asset != "USDT":
                continue

            actual_symbol = str(symbol_info.get("symbol", "")).upper()
            display_symbol = str(token_item.get("symbol", "")).upper()
            legacy_display_symbol = f"{display_symbol}USDT"
            price = float(token_item.get("price", 0.0) or 0.0)
            liquidity = float(token_item.get("liquidity", 0.0) or 0.0)
            if not actual_symbol or not display_symbol or price <= 0:
                continue
            if liquidity < self.settings.alpha_min_liquidity_usdt:
                continue
            if legacy_display_symbol:
                alias_map[legacy_display_symbol] = display_symbol
            alias_map[actual_symbol] = display_symbol
            actual_symbol_map[display_symbol] = actual_symbol

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

        filtered = await self._filter_alpha_snapshots_by_market_activity(client, snapshots, actual_symbol_map)
        self._latest_alpha_symbol_aliases = alias_map
        self._latest_alpha_actual_symbols = {row.symbol: actual_symbol_map[row.symbol] for row in filtered if row.symbol in actual_symbol_map}
        return filtered

    async def _filter_alpha_snapshots_by_market_activity(
        self,
        client: httpx.AsyncClient,
        snapshots: list[SymbolSnapshot],
        actual_symbol_map: dict[str, str],
    ) -> list[SymbolSnapshot]:
        filtered: list[SymbolSnapshot] = []
        for row in snapshots:
            actual_symbol = actual_symbol_map.get(row.symbol)
            if not actual_symbol:
                continue
            ticker_payload = await self._fetch_json_with_retry(
                client,
                f"https://www.binance.com/bapi/defi/v1/public/alpha-trade/ticker?symbol={actual_symbol}",
                retries=1,
            )
            klines_payload = await self._fetch_json_with_retry(
                client,
                f"https://www.binance.com/bapi/defi/v1/public/alpha-trade/klines?symbol={actual_symbol}&interval=1d&limit=30",
                retries=1,
            )
            if not self._passes_alpha_market_activity_filter(ticker_payload, klines_payload):
                continue
            ticker_data = ticker_payload.get("data", {}) if isinstance(ticker_payload, dict) else {}
            row.price = float(ticker_data.get("lastPrice", row.price) or row.price)
            row.volume_24h = float(ticker_data.get("quoteVolume", row.volume_24h) or row.volume_24h)
            row.change_pct_24h = float(ticker_data.get("priceChangePercent", row.change_pct_24h) or row.change_pct_24h)
            # Alpha 准入：只接受 24h 有明显方向性波动的标的（±3%），过滤横盘噪声。
            if abs(row.change_pct_24h) < 3.0:
                continue
            filtered.append(row)
        return filtered

    def _passes_alpha_market_activity_filter(self, ticker_payload: Any, klines_payload: Any) -> bool:
        if not isinstance(ticker_payload, dict) or ticker_payload.get("code") != "000000":
            return False
        if not isinstance(klines_payload, dict) or klines_payload.get("code") != "000000":
            return False
        ticker_data = ticker_payload.get("data", {}) or {}
        klines_data = klines_payload.get("data", []) or []
        try:
            quote_volume_24h = float(ticker_data.get("quoteVolume", 0.0) or 0.0)
            trade_count_24h = int(ticker_data.get("count", 0) or 0)
        except (TypeError, ValueError):
            return False
        daily_quote_volumes: list[float] = []
        for row in klines_data:
            if not isinstance(row, list) or len(row) < 9:
                continue
            try:
                daily_quote_volumes.append(float(row[7] or 0.0))
            except (TypeError, ValueError):
                continue
        if not daily_quote_volumes:
            return False
        ordered = sorted(daily_quote_volumes)
        median_daily_quote_volume = ordered[len(ordered) // 2]
        return (
            quote_volume_24h >= self.settings.alpha_min_quote_volume_24h_usdt
            and trade_count_24h >= self.settings.alpha_min_trade_count_24h
            and median_daily_quote_volume >= self.settings.alpha_min_median_daily_quote_volume_30d_usdt
        )

    @staticmethod
    def _extract_spot_trading_symbols(exchange_info_payload: dict) -> set[str]:
        symbols: set[str] = set()
        for item in exchange_info_payload.get("symbols", []) or []:
            symbol = str(item.get("symbol", "")).upper()
            if not symbol:
                continue
            if item.get("status") != "TRADING":
                continue
            if str(item.get("quoteAsset", "")).upper() != "USDT":
                continue
            if item.get("isSpotTradingAllowed") is False:
                continue
            symbols.add(symbol)
        return symbols

    @staticmethod
    def _extract_perpetual_trading_symbols(exchange_info_payload: dict) -> set[str]:
        symbols: set[str] = set()
        for item in exchange_info_payload.get("symbols", []) or []:
            symbol = str(item.get("symbol", "")).upper()
            if not symbol:
                continue
            if item.get("status") != "TRADING":
                continue
            if str(item.get("quoteAsset", "")).upper() != "USDT":
                continue
            if str(item.get("contractType", "")).upper() != "PERPETUAL":
                continue
            symbols.add(symbol)
        return symbols

    def _should_exclude_symbol(self, symbol: str, market_type: MarketType) -> bool:
        if market_type not in {MarketType.spot, MarketType.perpetual}:
            return False
        upper_symbol = symbol.upper()
        if upper_symbol in self.settings.excluded_large_cap_symbol_set:
            return True
        if upper_symbol.endswith("USDT"):
            base_asset = upper_symbol[:-4]
            if base_asset in self.settings.excluded_stablecoin_base_set:
                return True
        return False

