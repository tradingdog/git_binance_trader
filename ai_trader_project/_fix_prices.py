"""一次性修复脚本：将引擎中的错误虚假价格替换为真实市场参考价格"""
import ast
from pathlib import Path

engine = Path(__file__).parent / "src/ai_trader_project/engine.py"
raw = engine.read_bytes()
has_bom = raw.startswith(b'\xef\xbb\xbf')
content = raw[3:].decode('utf-8') if has_bom else raw.decode('utf-8')

# ==========================================
# 修复1: _open_mock_position 候选列表改为真实价格/数量
# ==========================================
old1 = (
    '        candidates = [\n'
    '            ("BTCUSDT", MarketType.spot, 1),\n'
    '            ("ETHUSDT", MarketType.spot, 1),\n'
    '            ("SOLUSDT", MarketType.perpetual, 3),\n'
    '            ("DOGEUSDT", MarketType.perpetual, 3),\n'
    '            ("AIUSDT", MarketType.alpha, 2),\n'
    '            ("WLDUSDT", MarketType.alpha, 2),\n'
    '        ]\n'
    '        available = [item for item in candidates if item[0] not in self._position_book]\n'
    '        if not available:\n'
    '            return\n'
    '        symbol, market_type, leverage = self._rng.choice(available)\n'
    '        price = round(self._rng.uniform(8, 160), 4)\n'
    '        quantity = round(self._rng.uniform(0.4, 1.8), 6)\n'
    '        margin = price * quantity / max(1, leverage)'
)
new1 = (
    '        # (symbol, market_type, leverage, price_lo, price_hi, qty_lo, qty_hi)\n'
    '        # 价格范围参考2026年4月真实市场水平；数量确保单笔保证金约200-600 USDT\n'
    '        candidates = [\n'
    '            ("BTCUSDT",  MarketType.spot,      1, 68_000, 74_000, 0.003, 0.008),\n'
    '            ("ETHUSDT",  MarketType.spot,      1,  3_200,  3_600, 0.06,  0.15),\n'
    '            ("SOLUSDT",  MarketType.perpetual, 3,    140,    160, 4.0,   10.0),\n'
    '            ("DOGEUSDT", MarketType.perpetual, 3,   0.15,   0.25, 3_000, 7_000),\n'
    '            ("AIUSDT",   MarketType.alpha,     2,    0.5,    1.5, 300,   800),\n'
    '            ("WLDUSDT",  MarketType.alpha,     2,    1.5,    3.0, 150,   400),\n'
    '        ]\n'
    '        available = [item for item in candidates if item[0] not in self._position_book]\n'
    '        if not available:\n'
    '            return\n'
    '        symbol, market_type, leverage, price_lo, price_hi, qty_lo, qty_hi = self._rng.choice(available)\n'
    '        price = round(self._rng.uniform(price_lo, price_hi), 4)\n'
    '        quantity = round(self._rng.uniform(qty_lo, qty_hi), 6)\n'
    '        margin = price * quantity / max(1, leverage)'
)
assert old1 in content, 'Pattern1 not found'
content = content.replace(old1, new1, 1)
print('Fix1 applied: _open_mock_position realistic prices')

# ==========================================
# 修复2: _append_market_timeseries 行情时序真实价格
# ==========================================
old2 = (
    '    def _append_market_timeseries(self, now_ts: datetime) -> None:\n'
    '        symbols = ["BTCUSDT", "ETHUSDT", "SOLUSDT", "DOGEUSDT"]\n'
    '        for sym in symbols:\n'
    '            base = self._rng.uniform(10, 120)\n'
    '            op = round(base, 4)\n'
    '            cl = round(base * (1 + self._rng.uniform(-0.01, 0.01)), 4)\n'
    '            hi = round(max(op, cl) * (1 + self._rng.uniform(0.0, 0.005)), 4)\n'
    '            lo = round(min(op, cl) * (1 - self._rng.uniform(0.0, 0.005)), 4)\n'
    '            vol = round(self._rng.uniform(1200, 8800), 4)'
)
new2 = (
    '    # 各交易对真实参考价格区间（2026年4月）与成交量区间（以基础币计）\n'
    '    _TIMESERIES_PRICE_RANGES: dict[str, tuple[float, float]] = {\n'
    '        "BTCUSDT":  (68_000, 74_000),\n'
    '        "ETHUSDT":  ( 3_200,  3_600),\n'
    '        "SOLUSDT":  (   140,    160),\n'
    '        "DOGEUSDT": (  0.15,   0.25),\n'
    '    }\n'
    '    _TIMESERIES_VOL_RANGES: dict[str, tuple[float, float]] = {\n'
    '        "BTCUSDT":  (     50,     300),\n'
    '        "ETHUSDT":  (    500,   3_000),\n'
    '        "SOLUSDT":  (  5_000,  50_000),\n'
    '        "DOGEUSDT": (500_000, 5_000_000),\n'
    '    }\n'
    '\n'
    '    def _append_market_timeseries(self, now_ts: datetime) -> None:\n'
    '        for sym, (price_lo, price_hi) in self._TIMESERIES_PRICE_RANGES.items():\n'
    '            base = self._rng.uniform(price_lo, price_hi)\n'
    '            op = round(base, 4)\n'
    '            cl = round(base * (1 + self._rng.uniform(-0.01, 0.01)), 4)\n'
    '            hi = round(max(op, cl) * (1 + self._rng.uniform(0.0, 0.005)), 4)\n'
    '            lo = round(min(op, cl) * (1 - self._rng.uniform(0.0, 0.005)), 4)\n'
    '            vol_lo, vol_hi = self._TIMESERIES_VOL_RANGES[sym]\n'
    '            vol = round(self._rng.uniform(vol_lo, vol_hi), 4)'
)
assert old2 in content, 'Pattern2 not found'
content = content.replace(old2, new2, 1)
print('Fix2 applied: _append_market_timeseries realistic prices')

ast.parse(content)
print('syntax OK')

engine.write_bytes((b'\xef\xbb\xbf' if has_bom else b'') + content.encode('utf-8'))
print('written OK')
