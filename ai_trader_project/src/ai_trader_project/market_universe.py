from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any
from urllib.error import URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from .models import MarketType


@dataclass
class MarketCandidate:
    symbol: str
    market_type: MarketType
    leverage: int
    price: float
    volume_24h: float
    change_pct_24h: float


class MarketUniverseBuilder:
    # 与人类版本保持一致：剔除头部20大盘币 + 稳定币资产。
    EXCLUDED_LARGE_CAP_SYMBOLS = {
        "BTCUSDT",
        "ETHUSDT",
        "BNBUSDT",
        "XRPUSDT",
        "SOLUSDT",
        "ADAUSDT",
        "DOGEUSDT",
        "TRXUSDT",
        "LINKUSDT",
        "TONUSDT",
        "AVAXUSDT",
        "SHIBUSDT",
        "BCHUSDT",
        "DOTUSDT",
        "XLMUSDT",
        "SUIUSDT",
        "LTCUSDT",
        "HBARUSDT",
        "UNIUSDT",
        "XMRUSDT",
    }
    EXCLUDED_STABLECOIN_BASES = {
        "USDC",
        "FDUSD",
        "TUSD",
        "USDP",
        "USDS",
        "DAI",
        "BUSD",
        "USDE",
        "PYUSD",
    }

    ALPHA_MIN_LIQUIDITY_USDT = 5_000_000.0
    ALPHA_MIN_QUOTE_VOLUME_24H_USDT = 500_000.0
    MAX_ALPHA_SYMBOLS_TO_SCAN = 40

    def __init__(self, timeout_seconds: float = 8.0) -> None:
        self.timeout_seconds = timeout_seconds

    def build(self, limit: int = 300) -> list[MarketCandidate]:
        # 为避免低内存机器 OOM，统一使用轻量 price 端点构建主市场池。
        spot_tickers = self._get_json("https://api.binance.com/api/v3/ticker/price")
        perp_tickers = self._get_json("https://fapi.binance.com/fapi/v1/ticker/price")
        spot_info = self._get_json("https://api.binance.com/api/v3/exchangeInfo")
        perp_info = self._get_json("https://fapi.binance.com/fapi/v1/exchangeInfo")

        if not isinstance(spot_tickers, list) or not isinstance(perp_tickers, list):
            return []

        spot_trading = self._extract_spot_trading_symbols(spot_info if isinstance(spot_info, dict) else {})
        perp_trading = self._extract_perpetual_trading_symbols(perp_info if isinstance(perp_info, dict) else {})

        rows: list[MarketCandidate] = []
        rows.extend(self._build_spot_candidates(spot_tickers, spot_trading))
        rows.extend(self._build_perpetual_candidates(perp_tickers, perp_trading))
        rows.extend(self._build_alpha_candidates())

        rows.sort(key=lambda r: (1 if r.market_type == MarketType.alpha else 0, r.symbol), reverse=True)
        if limit > 0:
            rows = rows[:limit]
        return rows

    def _build_spot_candidates(self, payload: list[dict[str, Any]], trading_symbols: set[str]) -> list[MarketCandidate]:
        out: list[MarketCandidate] = []
        for item in payload:
            symbol = str(item.get("symbol", "")).upper()
            if symbol not in trading_symbols:
                continue
            if not symbol.endswith("USDT"):
                continue
            if self._should_exclude_symbol(symbol):
                continue
            price = self._as_float(item.get("lastPrice") or item.get("price"))
            if price <= 0:
                continue
            out.append(
                MarketCandidate(
                    symbol=symbol,
                    market_type=MarketType.spot,
                    leverage=1,
                    price=price,
                    volume_24h=0.0,
                    change_pct_24h=0.0,
                )
            )
        return out

    def _build_perpetual_candidates(self, payload: list[dict[str, Any]], trading_symbols: set[str]) -> list[MarketCandidate]:
        out: list[MarketCandidate] = []
        for item in payload:
            symbol = str(item.get("symbol", "")).upper()
            if symbol not in trading_symbols:
                continue
            if not symbol.endswith("USDT"):
                continue
            if self._should_exclude_symbol(symbol):
                continue
            price = self._as_float(item.get("lastPrice") or item.get("price"))
            if price <= 0:
                continue
            out.append(
                MarketCandidate(
                    symbol=symbol,
                    market_type=MarketType.perpetual,
                    leverage=3,
                    price=price,
                    volume_24h=0.0,
                    change_pct_24h=0.0,
                )
            )
        return out

    def _build_alpha_candidates(self) -> list[MarketCandidate]:
        token_payload = self._get_json(
            "https://www.binance.com/bapi/defi/v1/public/wallet-direct/buw/wallet/cex/alpha/all/token/list"
        )
        info_payload = self._get_json("https://www.binance.com/bapi/defi/v1/public/alpha-trade/get-exchange-info")

        if not isinstance(token_payload, dict) or token_payload.get("code") != "000000":
            return []
        if not isinstance(info_payload, dict) or info_payload.get("code") != "000000":
            return []

        token_by_alpha_id: dict[str, dict[str, Any]] = {}
        for item in token_payload.get("data", []) or []:
            alpha_id = str(item.get("alphaId", "")).upper()
            if alpha_id:
                token_by_alpha_id[alpha_id] = item

        out: list[MarketCandidate] = []
        pending: list[tuple[float, str, str, float, float, float]] = []
        symbols = info_payload.get("data", {}).get("symbols", []) or []
        for symbol_info in symbols:
            if symbol_info.get("status") != "TRADING":
                continue
            base_asset = str(symbol_info.get("baseAsset", "")).upper()
            quote_asset = str(symbol_info.get("quoteAsset", "")).upper()
            if quote_asset != "USDT":
                continue
            token_item = token_by_alpha_id.get(base_asset)
            if not token_item:
                continue

            actual_symbol = str(symbol_info.get("symbol", "")).upper()
            display_symbol = str(token_item.get("symbol", "")).upper()
            if not actual_symbol or not display_symbol:
                continue
            liquidity = self._as_float(token_item.get("liquidity"))
            price = self._as_float(token_item.get("price"))
            change = self._as_float(token_item.get("percentChange24h"))
            volume = self._as_float(token_item.get("volume24h"))
            if liquidity < self.ALPHA_MIN_LIQUIDITY_USDT:
                continue
            if volume < self.ALPHA_MIN_QUOTE_VOLUME_24H_USDT:
                continue
            if abs(change) < 10.0:
                continue
            pending.append((liquidity, actual_symbol, display_symbol, price, change, volume))

        pending.sort(key=lambda row: row[0], reverse=True)
        for _, _, display_symbol, price, change, volume in pending[: self.MAX_ALPHA_SYMBOLS_TO_SCAN]:
            if price <= 0:
                continue
            out.append(
                MarketCandidate(
                    symbol=display_symbol,
                    market_type=MarketType.alpha,
                    leverage=1,
                    price=price,
                    volume_24h=volume,
                    change_pct_24h=change,
                )
            )
        return out

    @staticmethod
    def _extract_spot_trading_symbols(exchange_info_payload: dict[str, Any]) -> set[str]:
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
    def _extract_perpetual_trading_symbols(exchange_info_payload: dict[str, Any]) -> set[str]:
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

    def _should_exclude_symbol(self, symbol: str) -> bool:
        upper_symbol = symbol.upper()
        if upper_symbol in self.EXCLUDED_LARGE_CAP_SYMBOLS:
            return True
        if upper_symbol.endswith("USDT"):
            base_asset = upper_symbol[:-4]
            if base_asset in self.EXCLUDED_STABLECOIN_BASES:
                return True
        return False

    def _get_json(self, url: str, query: dict[str, Any] | None = None) -> Any:
        if query:
            url = f"{url}?{urlencode(query)}"
        req = Request(url, headers={"User-Agent": "git-binance-trader-ai/1.0"})
        try:
            with urlopen(req, timeout=self.timeout_seconds) as response:
                return json.loads(response.read())
        except (URLError, TimeoutError, OSError, ValueError):
            return None

    @staticmethod
    def _as_float(value: Any) -> float:
        try:
            return float(value or 0.0)
        except (TypeError, ValueError):
            return 0.0
