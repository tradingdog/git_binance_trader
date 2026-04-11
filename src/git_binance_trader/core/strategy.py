from __future__ import annotations

from collections import defaultdict, deque
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from math import log10

from git_binance_trader.core.models import LiquidityType, MarketType, Position, Side, SymbolSnapshot, Trade


@dataclass
class AdaptiveParams:
    max_positions: int = 3
    max_exposure_pct: float = 50.0
    target_margin_utilization_pct: float = 35.0
    entry_score_threshold: float = 3.2
    rotation_exit_score: float = 1.6
    position_budget_pct: float = 10.0
    min_quote_volume: float = 150_000_000.0
    perpetual_leverage: int = 3


class OpportunityStrategy:
    name = "trend_momentum_v3"
    STRATEGY_VERSION = 2
    # ── 仓位与敞口 ──
    MIN_MAX_POSITIONS = 2
    MAX_MAX_POSITIONS = 5
    MIN_MAX_EXPOSURE_PCT = 45.0
    MAX_MAX_EXPOSURE_PCT = 65.0
    MIN_TARGET_MARGIN_UTILIZATION_PCT = 30.0
    MAX_TARGET_MARGIN_UTILIZATION_PCT = 55.0
    MIN_POSITION_BUDGET_PCT = 8.0
    # ── 决策节流 ──
    DECISION_INTERVAL_SECONDS = 60
    # ── 冷却与频率控制 ──
    REENTRY_COOLDOWN_SECONDS = 10 * 60
    ROTATION_REENTRY_COOLDOWN_SECONDS = 45 * 60
    MIN_HOLD_SECONDS = 20 * 60
    MAX_TRADES_PER_SYMBOL_PER_HOUR = 3
    STOPLOSS_QUARANTINE_SECONDS = 3 * 60 * 60
    STOPLOSS_QUARANTINE_THRESHOLD = 2
    MAX_CHASE_24H_PCT = 14.0
    MIN_SHORT_TREND_CONFIRM_PCT = 0.18
    LOSS_STREAK_LOOKBACK_SECONDS = 90 * 60
    LOSS_STREAK_PENALTY_STEP = 0.6
    QUALITY_THRESHOLD_UPLIFT = 0.15
    # ── 趋势退出参数 ──
    TREND_EXIT_MIN_HOLD_SECONDS = 20 * 60
    FLAT_POSITION_TIMEOUT_SECONDS = 90 * 60
    FLAT_POSITION_THRESHOLD_PCT = 0.5
    PROFIT_PROTECT_TRIGGER_PCT = 1.8
    PROFIT_PROTECT_EXIT_PCT = 0.3
    # ── 均线参数 ──
    MA_SHORT_MINUTES = 8.0
    MA_MID_MINUTES = 25.0

    def __init__(self) -> None:
        self.risk_per_trade_pct = 0.35
        self.params = AdaptiveParams()
        self._enforce_param_floors()
        self._series: dict[str, deque[tuple[float, float, float]]] = defaultdict(lambda: deque(maxlen=720))
        self._first_seen_ts: dict[str, datetime] = {}
        self._last_adapt_hour: str | None = None
        self._last_adaptation_event: dict[str, object] | None = None
        self._latest_adaptation_snapshot: dict[str, object] | None = None
        self._weak_score_streak: dict[str, int] = {}
        self._last_decision_ts: datetime | None = None
        self._position_high_water: dict[str, float] = {}

    def decide(
        self,
        *,
        watchlist: list[SymbolSnapshot],
        positions: dict[str, Position],
        cash: float,
        equity: float,
        recent_trades: list[Trade] | None = None,
        now_ts: datetime | None = None,
    ) -> tuple[list[Trade], str]:
        now = now_ts or datetime.now(timezone.utc)
        trades: list[Trade] = []
        insights: list[str] = []
        self._ingest_watchlist(watchlist, now)
        self._adapt_hourly(recent_trades or [], now)
        self._update_position_high_water(positions)

        # Decision throttle — collect data every cycle but decide less often
        if self._last_decision_ts is not None:
            elapsed = (now - self._last_decision_ts).total_seconds()
            if elapsed < self.DECISION_INTERVAL_SECONDS:
                return [], "数据采集中，等待决策窗口"
        self._last_decision_ts = now

        scored = self._score_candidates(watchlist, now)

        exits = self._build_trend_exits(positions, recent_trades or [], now)
        trades.extend(exits)
        if exits:
            insights.append(f"趋势退出 {len(exits)} 笔")

        exposure = self._current_exposure_pct(positions, equity)
        margin_util = self._current_margin_utilization_pct(positions, equity)
        room = max(0.0, self.params.max_exposure_pct - exposure)
        margin_room = max(0.0, self.params.target_margin_utilization_pct - margin_util)
        slots = max(0, self.params.max_positions - len(positions))

        if slots == 0 or room <= 0 or margin_room <= 0:
            return trades, "; ".join(insights) if insights else "仓位已满，等待信号"

        for snapshot, score in scored:
            symbol_key = f"{snapshot.market_type.value}:{snapshot.symbol}"
            if any(
                position.symbol == snapshot.symbol and position.market_type == snapshot.market_type
                for position in positions.values()
            ):
                continue
            if slots <= 0 or room <= 0:
                break
            if self._in_reentry_cooldown(symbol_key, recent_trades, now):
                continue
            if self._in_rotation_reentry_cooldown(symbol_key, recent_trades, now):
                continue
            if self._symbol_trade_count_within(symbol_key, recent_trades, now, 3600) >= self.MAX_TRADES_PER_SYMBOL_PER_HOUR:
                continue
            if self._in_stoploss_quarantine(symbol_key, recent_trades, now):
                continue
            if self._is_chasing_risk(symbol_key, snapshot):
                continue
            if not self._is_trend_confirmed(symbol_key, snapshot):
                continue

            effective_score = score - self._loss_streak_penalty(symbol_key, recent_trades, now)
            if effective_score < self.params.entry_score_threshold + self.QUALITY_THRESHOLD_UPLIFT:
                continue
            if snapshot.volume_24h < self.params.min_quote_volume:
                continue

            position_budget_pct = min(self.params.position_budget_pct, room / slots)
            max_budget_by_margin = self._max_budget_by_margin_room(snapshot.market_type, margin_room)
            position_budget_pct = min(position_budget_pct, max_budget_by_margin)
            notional = equity * position_budget_pct / 100
            notional = min(notional, cash)
            if notional <= 20:
                break

            quantity = round(notional / snapshot.price, 6)
            if quantity <= 0:
                continue

            note = f"机会开仓 score={effective_score:.2f} risk={self.risk_per_trade_pct:.2f}%"
            trades.append(
                Trade(
                    symbol=snapshot.symbol,
                    side=Side.buy,
                    quantity=quantity,
                    price=snapshot.price,
                    market_type=snapshot.market_type,
                    leverage=self._select_leverage(snapshot.market_type),
                    liquidity_type=LiquidityType.maker,
                    strategy=self.name,
                    note=note,
                )
            )
            insights.append(f"新开仓 {snapshot.symbol} score={effective_score:.2f} model={snapshot.market_type.value}")
            room -= position_budget_pct
            margin_room -= self._margin_consumption_pct(snapshot.market_type, position_budget_pct)
            slots -= 1

        if not insights:
            insights.append("未发现满足条件的新机会")
        return trades, "; ".join(insights)

    def export_state(self) -> dict[str, object]:
        return {
            "version": self.STRATEGY_VERSION,
            "risk_per_trade_pct": self.risk_per_trade_pct,
            "params": asdict(self.params),
            "last_adapt_hour": self._last_adapt_hour,
            "last_adaptation_event": self._last_adaptation_event,
            "latest_adaptation_snapshot": self._latest_adaptation_snapshot,
            "first_seen_ts": {k: v.isoformat() for k, v in self._first_seen_ts.items()},
            "weak_score_streak": self._weak_score_streak,
            "series": {k: list(v) for k, v in self._series.items()},
            "last_decision_ts": self._last_decision_ts.isoformat() if self._last_decision_ts else None,
            "position_high_water": dict(self._position_high_water),
        }

    def import_state(self, payload: dict[str, object]) -> bool:
        if not isinstance(payload, dict):
            return False
        try:
            self.risk_per_trade_pct = float(payload.get("risk_per_trade_pct", self.risk_per_trade_pct))
        except (TypeError, ValueError):
            return False

        saved_version = payload.get("version", 1)
        if saved_version != self.STRATEGY_VERSION:
            # Strategy version changed — reset adaptive params to new defaults
            self.params = AdaptiveParams()
            self._enforce_param_floors()
        else:
            params_payload = payload.get("params", {})
            if isinstance(params_payload, dict):
                try:
                    self.params = AdaptiveParams(**params_payload)
                    self._enforce_param_floors()
                except Exception:
                    return False

        self._last_adapt_hour = payload.get("last_adapt_hour") if isinstance(payload.get("last_adapt_hour"), str) else None
        self._last_adaptation_event = payload.get("last_adaptation_event") if isinstance(payload.get("last_adaptation_event"), dict) else None
        self._latest_adaptation_snapshot = (
            payload.get("latest_adaptation_snapshot")
            if isinstance(payload.get("latest_adaptation_snapshot"), dict)
            else None
        )

        self._first_seen_ts.clear()
        first_seen_payload = payload.get("first_seen_ts", {})
        if isinstance(first_seen_payload, dict):
            for key, value in first_seen_payload.items():
                if not isinstance(key, str) or not isinstance(value, str):
                    continue
                try:
                    self._first_seen_ts[key] = datetime.fromisoformat(value)
                except ValueError:
                    continue

        self._weak_score_streak.clear()
        weak_score_payload = payload.get("weak_score_streak", {})
        if isinstance(weak_score_payload, dict):
            for key, value in weak_score_payload.items():
                if isinstance(key, str) and isinstance(value, int):
                    self._weak_score_streak[key] = max(0, value)

        self._series.clear()
        series_payload = payload.get("series", {})
        if isinstance(series_payload, dict):
            for key, rows in series_payload.items():
                if not isinstance(key, str) or not isinstance(rows, list):
                    continue
                target = deque(maxlen=720)
                for row in rows[-720:]:
                    if not isinstance(row, (list, tuple)) or len(row) != 3:
                        continue
                    try:
                        target.append((float(row[0]), float(row[1]), float(row[2])))
                    except (TypeError, ValueError):
                        continue
                self._series[key] = target

        # Restore new v2 fields
        last_dec = payload.get("last_decision_ts")
        if isinstance(last_dec, str):
            try:
                self._last_decision_ts = datetime.fromisoformat(last_dec)
            except ValueError:
                pass

        self._position_high_water.clear()
        hw_payload = payload.get("position_high_water", {})
        if isinstance(hw_payload, dict):
            for key, value in hw_payload.items():
                if isinstance(key, str):
                    try:
                        self._position_high_water[key] = float(value)
                    except (TypeError, ValueError):
                        continue

        return True

    def _score_candidates(self, watchlist: list[SymbolSnapshot], now: datetime | None = None) -> list[tuple[SymbolSnapshot, float]]:
        now_ts = now or datetime.now(timezone.utc)
        candidates = [item for item in watchlist if item.price > 0]
        best_by_market_symbol: dict[str, tuple[SymbolSnapshot, float]] = {}
        by_symbol: dict[str, list[SymbolSnapshot]] = defaultdict(list)
        for item in candidates:
            by_symbol[item.symbol].append(item)

        for item in candidates:
            factors = self._compute_factors(item, by_symbol[item.symbol], now_ts)
            if item.market_type == MarketType.spot:
                score = self._score_spot(factors)
            elif item.market_type == MarketType.perpetual:
                score = self._score_perpetual(factors, item.funding_rate)
            else:
                score = self._score_alpha(factors)
            score = max(min(score, 20.0), -4.0)
            market_symbol_key = f"{item.market_type.value}:{item.symbol}"
            existing = best_by_market_symbol.get(market_symbol_key)
            if existing is None or score > existing[1]:
                best_by_market_symbol[market_symbol_key] = (item, score)
        return sorted(best_by_market_symbol.values(), key=lambda row: row[1], reverse=True)

    def _compute_factors(
        self,
        snapshot: SymbolSnapshot,
        same_symbol_items: list[SymbolSnapshot],
        now: datetime,
    ) -> dict[str, float]:
        key = f"{snapshot.market_type.value}:{snapshot.symbol}"
        series = list(self._series[key])

        momentum = max(min(snapshot.change_pct_24h, 18.0), -18.0) / 6.0
        historical_volumes = [row[1] for row in series[:-1]] or [snapshot.volume_24h]
        avg_volume = max(sum(historical_volumes) / max(len(historical_volumes), 1), 1.0)
        volume_surge = max(min(snapshot.volume_24h / avg_volume - 1.0, 6.0), -1.0)

        recent_prices = [row[0] for row in series[-18:]]
        short_trend = 0.0
        if len(recent_prices) >= 6:
            hi = max(recent_prices)
            lo = min(recent_prices)
            spread_pct = (hi - lo) / max(snapshot.price, 1e-9)
            squeeze_score = max(0.0, 0.06 - spread_pct) / 0.06
            head = max(recent_prices[0], 1e-9)
            short_trend_pct = (recent_prices[-1] / head - 1.0) * 100
            short_trend = max(min(short_trend_pct / 0.8, 2.0), -2.0)
        else:
            squeeze_score = 0.0
        breakout = max(0.0, momentum)
        volatility_breakout = squeeze_score * breakout

        other_changes = [item.change_pct_24h for item in same_symbol_items if item.market_type != snapshot.market_type]
        cross_market_strength = snapshot.change_pct_24h - (sum(other_changes) / len(other_changes) if other_changes else 0.0)
        cross_market_strength /= 6.0

        # 社交热度代理：成交量、排名、alpha 热点加权。
        rank_bonus = 1.5 / max(snapshot.market_cap_rank, 1)
        social_heat = log10(max(snapshot.volume_24h, 1.0)) / 4.0 + rank_bonus
        if snapshot.market_type == MarketType.alpha:
            social_heat += 0.25

        first_seen = self._first_seen_ts.get(key, now)
        age_hours = max((now - first_seen).total_seconds() / 3600.0, 0.0)
        new_coin_behavior = 0.0
        if age_hours <= 24:
            new_coin_behavior = 1.0
        elif age_hours <= 24 * 7:
            new_coin_behavior = 0.35

        mean_reversion_risk = 0.0
        if snapshot.change_pct_24h > 10.0 and short_trend < 0:
            mean_reversion_risk = min(1.8, (snapshot.change_pct_24h - 10.0) / 6.5 + abs(short_trend) * 0.7)

        return {
            "momentum": momentum,
            "volume_surge": volume_surge,
            "volatility_breakout": volatility_breakout,
            "cross_market_strength": cross_market_strength,
            "social_heat": social_heat,
            "new_coin_behavior": new_coin_behavior,
            "short_trend": short_trend,
            "mean_reversion_risk": mean_reversion_risk,
            "liquidity": max(min(log10(max(snapshot.volume_24h, 1.0)) / 6.0, 2.0), 0.0),
        }

    @staticmethod
    def _score_spot(f: dict[str, float]) -> float:
        return (
            f["momentum"] * 1.4
            + f["volume_surge"] * 1.1
            + f["volatility_breakout"] * 1.0
            + f["cross_market_strength"] * 0.8
            + f["social_heat"] * 0.5
            + f["short_trend"] * 0.9
            - f["mean_reversion_risk"] * 0.9
            + f["liquidity"] * 0.8
        )

    @staticmethod
    def _score_perpetual(f: dict[str, float], funding_rate: float) -> float:
        funding_penalty = max(funding_rate, 0.0) * 800
        return (
            f["momentum"] * 1.2
            + f["volume_surge"] * 1.0
            + f["volatility_breakout"] * 0.9
            + f["cross_market_strength"] * 1.25
            + f["social_heat"] * 0.4
            + f["short_trend"] * 1.1
            - f["mean_reversion_risk"] * 1.2
            + f["liquidity"] * 0.9
            - funding_penalty
        )

    @staticmethod
    def _score_alpha(f: dict[str, float]) -> float:
        return (
            f["momentum"] * 1.0
            + f["volume_surge"] * 1.25
            + f["volatility_breakout"] * 0.7
            + f["cross_market_strength"] * 0.55
            + f["social_heat"] * 1.15
            + f["new_coin_behavior"] * 1.4
            + f["short_trend"] * 0.95
            - f["mean_reversion_risk"] * 0.8
            + f["liquidity"] * 0.7
        )

    def _build_trend_exits(
        self,
        positions: dict[str, Position],
        recent_trades: list[Trade],
        now: datetime,
    ) -> list[Trade]:
        exits: list[Trade] = []
        for position in positions.values():
            key = f"{position.market_type.value}:{position.symbol}"
            open_age = self._position_open_age_seconds(key, recent_trades, now)
            if open_age is None:
                open_age = 0.0

            if open_age < self.TREND_EXIT_MIN_HOLD_SECONDS:
                continue

            pnl_pct = (position.current_price - position.entry_price) / max(position.entry_price, 1e-9) * 100
            high_water = self._position_high_water.get(key, 0.0)
            exit_reason: str | None = None

            # 1. Profit protection: unrealized peaked high then dropped
            if high_water >= self.PROFIT_PROTECT_TRIGGER_PCT and pnl_pct < self.PROFIT_PROTECT_EXIT_PCT:
                exit_reason = f"利润保护退出 peak={high_water:.1f}% now={pnl_pct:.1f}%"

            # 2. Flat position timeout: held too long without meaningful move
            elif open_age > self.FLAT_POSITION_TIMEOUT_SECONDS and abs(pnl_pct) < self.FLAT_POSITION_THRESHOLD_PCT:
                exit_reason = f"仓位停滞退出 age={open_age / 60:.0f}m pnl={pnl_pct:+.2f}%"

            # 3. Trend reversal: price below mid-term MA and not in significant profit
            elif open_age >= self.TREND_EXIT_MIN_HOLD_SECONDS:
                ma_mid = self._compute_ma(key, self.MA_MID_MINUTES)
                if ma_mid is not None and position.current_price < ma_mid and pnl_pct < 0.5:
                    exit_reason = f"趋势反转退出 price<MA{self.MA_MID_MINUTES:.0f} pnl={pnl_pct:+.2f}%"

            if exit_reason:
                exits.append(
                    Trade(
                        symbol=position.symbol,
                        side=Side.sell,
                        quantity=position.quantity,
                        price=position.current_price,
                        market_type=position.market_type,
                        leverage=position.leverage,
                        liquidity_type=LiquidityType.maker,
                        strategy=self.name,
                        note=exit_reason,
                    )
                )
                self._position_high_water.pop(key, None)
        return exits

    def _ingest_watchlist(self, watchlist: list[SymbolSnapshot], now: datetime) -> None:
        for item in watchlist:
            key = f"{item.market_type.value}:{item.symbol}"
            self._series[key].append((item.price, max(item.volume_24h, 1.0), item.change_pct_24h))
            self._first_seen_ts.setdefault(key, now)

    def _compute_ma(self, symbol_key: str, window_minutes: float) -> float | None:
        series = list(self._series.get(symbol_key, []))
        if len(series) < 12:
            return None
        points = int(window_minutes * 12)
        subset = series[-points:] if len(series) >= points else series
        prices = [row[0] for row in subset]
        return sum(prices) / len(prices) if prices else None

    def _is_trend_confirmed(self, symbol_key: str, snapshot: SymbolSnapshot) -> bool:
        ma_short = self._compute_ma(symbol_key, self.MA_SHORT_MINUTES)
        if ma_short is None:
            return False
        if snapshot.price < ma_short:
            return False
        series = list(self._series.get(symbol_key, []))
        if len(series) < 36:
            return False
        recent_avg = sum(row[0] for row in series[-6:]) / 6
        earlier_avg = sum(row[0] for row in series[-36:-30]) / max(len(series[-36:-30]), 1)
        return recent_avg > earlier_avg

    def _update_position_high_water(self, positions: dict[str, Position]) -> None:
        active_keys: set[str] = set()
        for position in positions.values():
            key = f"{position.market_type.value}:{position.symbol}"
            active_keys.add(key)
            pnl_pct = (position.current_price - position.entry_price) / max(position.entry_price, 1e-9) * 100
            self._position_high_water[key] = max(self._position_high_water.get(key, 0.0), pnl_pct)
        for key in list(self._position_high_water.keys()):
            if key not in active_keys:
                del self._position_high_water[key]

    def _adapt_hourly(self, recent_trades: list[Trade], now: datetime) -> None:
        hour_key = now.strftime("%Y%m%d%H")
        if self._last_adapt_hour == hour_key:
            return

        prev = AdaptiveParams(**asdict(self.params))
        window_start = now.timestamp() - 3600
        closed = [
            t
            for t in recent_trades
            if t.side == Side.sell and t.created_at.timestamp() >= window_start
        ]
        wins = [t for t in closed if t.realized_pnl > 0]
        realized_sum = sum(t.realized_pnl for t in closed)
        fee_sum = sum(t.fee_paid for t in closed)
        fee_ratio = fee_sum / max(abs(realized_sum), 1.0)
        fee_dominant = fee_sum > 0 and fee_ratio > 1.1
        win_rate = len(wins) / len(closed) if closed else 0.5
        avg_pnl = realized_sum / len(closed) if closed else 0.0

        # Recovery loosening: if no trades in the last hour, gently loosen
        if not closed:
            self.params.entry_score_threshold = max(3.0, self.params.entry_score_threshold - 0.15)
            self.params.position_budget_pct = min(14.0, self.params.position_budget_pct + 0.2)
        elif win_rate < 0.35 or avg_pnl < 0:
            # Mild tightening (reduced from previous aggressive steps)
            self.params.max_positions = max(self.MIN_MAX_POSITIONS, self.params.max_positions - 1)
            self.params.entry_score_threshold = min(5.5, self.params.entry_score_threshold + 0.2)
            self.params.position_budget_pct = max(
                self.MIN_POSITION_BUDGET_PCT,
                self.params.position_budget_pct - 0.3,
            )
            self.params.min_quote_volume = min(320_000_000.0, self.params.min_quote_volume * 1.05)
        elif win_rate > 0.5 and avg_pnl > 0:
            # Loosening on good performance
            self.params.max_positions = min(self.MAX_MAX_POSITIONS, self.params.max_positions + 1)
            self.params.max_exposure_pct = min(self.MAX_MAX_EXPOSURE_PCT, self.params.max_exposure_pct + 2.0)
            self.params.target_margin_utilization_pct = min(
                self.MAX_TARGET_MARGIN_UTILIZATION_PCT,
                self.params.target_margin_utilization_pct + 1.5,
            )
            self.params.entry_score_threshold = max(3.0, self.params.entry_score_threshold - 0.15)
            self.params.position_budget_pct = min(14.0, self.params.position_budget_pct + 0.3)
            self.params.min_quote_volume = max(80_000_000.0, self.params.min_quote_volume * 0.96)

        if closed and fee_dominant:
            self.params.entry_score_threshold = min(5.5, self.params.entry_score_threshold + 0.1)

        self._enforce_param_floors()

        self._last_adapt_hour = hour_key
        self._last_adaptation_event = {
            "timestamp": now.isoformat(),
            "hour": hour_key,
            "before": asdict(prev),
            "after": asdict(self.params),
            "metrics": {
                "closed_trades": len(closed),
                "win_rate": round(win_rate, 4),
                "avg_realized_pnl": round(avg_pnl, 6),
                "realized_sum": round(realized_sum, 6),
                "fee_sum": round(fee_sum, 6),
                "fee_ratio": round(fee_ratio, 4),
                "fee_dominant": fee_dominant,
            },
        }
        self._latest_adaptation_snapshot = self._last_adaptation_event

    def _enforce_param_floors(self) -> None:
        self.params.max_positions = max(self.MIN_MAX_POSITIONS, self.params.max_positions)
        self.params.max_exposure_pct = max(self.MIN_MAX_EXPOSURE_PCT, self.params.max_exposure_pct)
        self.params.target_margin_utilization_pct = max(
            self.MIN_TARGET_MARGIN_UTILIZATION_PCT,
            self.params.target_margin_utilization_pct,
        )
        self.params.position_budget_pct = max(self.MIN_POSITION_BUDGET_PCT, self.params.position_budget_pct)
        self.params.max_positions = min(self.MAX_MAX_POSITIONS, self.params.max_positions)
        self.params.max_exposure_pct = min(self.MAX_MAX_EXPOSURE_PCT, self.params.max_exposure_pct)
        self.params.target_margin_utilization_pct = min(
            self.MAX_TARGET_MARGIN_UTILIZATION_PCT,
            self.params.target_margin_utilization_pct,
        )

    def _in_reentry_cooldown(self, symbol_key: str, recent_trades: list[Trade], now: datetime) -> bool:
        cutoff = now.timestamp() - self.REENTRY_COOLDOWN_SECONDS
        for trade in reversed(recent_trades):
            if trade.created_at.timestamp() < cutoff:
                break
            if f"{trade.market_type.value}:{trade.symbol}" == symbol_key:
                return True
        return False

    def _in_rotation_reentry_cooldown(self, symbol_key: str, recent_trades: list[Trade], now: datetime) -> bool:
        cutoff = now.timestamp() - self.ROTATION_REENTRY_COOLDOWN_SECONDS
        for trade in reversed(recent_trades):
            if trade.created_at.timestamp() < cutoff:
                break
            if trade.side != Side.sell:
                continue
            if f"{trade.market_type.value}:{trade.symbol}" != symbol_key:
                continue
            if (trade.note or "").startswith("机会衰减退出"):
                return True
        return False

    def _in_stoploss_quarantine(self, symbol_key: str, recent_trades: list[Trade], now: datetime) -> bool:
        cutoff = now.timestamp() - self.STOPLOSS_QUARANTINE_SECONDS
        stop_count = 0
        for trade in reversed(recent_trades):
            if trade.created_at.timestamp() < cutoff:
                break
            if trade.side != Side.sell:
                continue
            if f"{trade.market_type.value}:{trade.symbol}" != symbol_key:
                continue
            if "止损" in (trade.note or ""):
                stop_count += 1
                if stop_count >= self.STOPLOSS_QUARANTINE_THRESHOLD:
                    return True
        return False

    def _is_chasing_risk(self, symbol_key: str, snapshot: SymbolSnapshot) -> bool:
        recent_trend_pct = self._recent_trend_pct(symbol_key)
        if recent_trend_pct is None:
            return False
        if recent_trend_pct <= -0.15:
            return True
        if snapshot.change_pct_24h >= self.MAX_CHASE_24H_PCT and recent_trend_pct <= self.MIN_SHORT_TREND_CONFIRM_PCT:
            return True
        return False

    def _recent_trend_pct(self, symbol_key: str) -> float | None:
        series = list(self._series.get(symbol_key, []))
        if len(series) < 6:
            return None
        head = max(series[-6][0], 1e-9)
        return (series[-1][0] / head - 1.0) * 100

    @staticmethod
    def _symbol_trade_count_within(
        symbol_key: str,
        recent_trades: list[Trade],
        now: datetime,
        window_seconds: int,
    ) -> int:
        cutoff = now.timestamp() - window_seconds
        count = 0
        for trade in reversed(recent_trades):
            if trade.created_at.timestamp() < cutoff:
                break
            if f"{trade.market_type.value}:{trade.symbol}" == symbol_key:
                count += 1
        return count

    @staticmethod
    def _position_open_age_seconds(symbol_key: str, recent_trades: list[Trade], now: datetime) -> float | None:
        for trade in reversed(recent_trades):
            if f"{trade.market_type.value}:{trade.symbol}" != symbol_key:
                continue
            if trade.side == Side.buy:
                return max(0.0, now.timestamp() - trade.created_at.timestamp())
            if trade.side == Side.sell:
                return None
        return None

    def _loss_streak_penalty(self, symbol_key: str, recent_trades: list[Trade], now: datetime) -> float:
        cutoff = now.timestamp() - self.LOSS_STREAK_LOOKBACK_SECONDS
        streak = 0
        for trade in reversed(recent_trades):
            if trade.created_at.timestamp() < cutoff:
                break
            if f"{trade.market_type.value}:{trade.symbol}" != symbol_key:
                continue
            if trade.side != Side.sell:
                continue
            note = trade.note or ""
            if "止损" in note:
                streak += 1
                continue
            break
        if streak < 2:
            return 0.0
        return min(1.8, streak * self.LOSS_STREAK_PENALTY_STEP)

    def get_and_clear_adaptation_event(self) -> dict[str, object] | None:
        event = self._last_adaptation_event
        self._last_adaptation_event = None
        return event

    def dashboard_meta(self, watchlist: list[SymbolSnapshot], now_ts: datetime | None = None) -> dict[str, object]:
        now = now_ts or datetime.now(timezone.utc)
        candidates = self._explain_hot_candidates(watchlist, now, limit=12)
        return {
            "factors": [
                {"key": "volume_surge", "label": "放量", "desc": "当前成交额相对历史均值的放大量级"},
                {"key": "volatility_breakout", "label": "波动挤压突破", "desc": "低波动挤压后向上突破强度"},
                {"key": "cross_market_strength", "label": "跨市场强弱", "desc": "同币种在现货/永续/Alpha 之间的相对强度"},
                {"key": "social_heat", "label": "社交热度代理", "desc": "按成交量、排名和 Alpha 热点构造的关注度"},
                {"key": "new_coin_behavior", "label": "新币行为", "desc": "新上线币种在不同阶段的行为溢价"},
                {"key": "short_trend", "label": "短周期趋势确认", "desc": "最近若干轮价格斜率，用于过滤追涨回落"},
                {"key": "mean_reversion_risk", "label": "均值回归风险", "desc": "24h 大涨但短周期走弱时的反转风险惩罚"},
            ],
            "adaptive_params": asdict(self.params),
            "latest_adaptation": self._latest_adaptation_snapshot,
            "hot_candidates": candidates,
            "strategy_name": self.name,
            "generated_at": now.isoformat(),
        }

    def _explain_hot_candidates(
        self,
        watchlist: list[SymbolSnapshot],
        now: datetime,
        limit: int,
    ) -> list[dict[str, object]]:
        candidates = [item for item in watchlist if item.price > 0]
        if not candidates:
            return []

        by_symbol: dict[str, list[SymbolSnapshot]] = defaultdict(list)
        for item in candidates:
            by_symbol[item.symbol].append(item)

        best_by_symbol: dict[str, dict[str, object]] = {}
        for item in candidates:
            factors = self._compute_factors(item, by_symbol[item.symbol], now)
            if item.market_type == MarketType.spot:
                score = self._score_spot(factors)
            elif item.market_type == MarketType.perpetual:
                score = self._score_perpetual(factors, item.funding_rate)
            else:
                score = self._score_alpha(factors)

            row = {
                "symbol": item.symbol,
                "market_type": item.market_type.value,
                "score": round(score, 4),
                "change_pct_24h": round(item.change_pct_24h, 4),
                "volume_24h": round(item.volume_24h, 2),
                "factors": {
                    "volume_surge": round(factors["volume_surge"], 4),
                    "volatility_breakout": round(factors["volatility_breakout"], 4),
                    "cross_market_strength": round(factors["cross_market_strength"], 4),
                    "social_heat": round(factors["social_heat"], 4),
                    "new_coin_behavior": round(factors["new_coin_behavior"], 4),
                    "short_trend": round(factors["short_trend"], 4),
                    "mean_reversion_risk": round(factors["mean_reversion_risk"], 4),
                },
            }

            existing = best_by_symbol.get(item.symbol)
            if existing is None or float(row["score"]) > float(existing["score"]):
                best_by_symbol[item.symbol] = row

        rows = sorted(best_by_symbol.values(), key=lambda r: float(r["score"]), reverse=True)
        return rows[: max(1, limit)]

    def _select_leverage(self, market_type: MarketType) -> int:
        if market_type == MarketType.perpetual:
            return self.params.perpetual_leverage
        return 1

    @staticmethod
    def _current_exposure_pct(positions: dict[str, Position], equity: float) -> float:
        if equity <= 0:
            return 0.0
        exposure = sum(position.market_value for position in positions.values())
        return exposure / equity * 100

    @staticmethod
    def _current_margin_utilization_pct(positions: dict[str, Position], equity: float) -> float:
        if equity <= 0:
            return 0.0
        margin_used = sum(position.margin_used for position in positions.values())
        return margin_used / equity * 100

    def _max_budget_by_margin_room(self, market_type: MarketType, margin_room_pct: float) -> float:
        if margin_room_pct <= 0:
            return 0.0
        if market_type == MarketType.perpetual:
            leverage = max(self.params.perpetual_leverage, 1)
            return margin_room_pct * leverage
        return margin_room_pct

    def _margin_consumption_pct(self, market_type: MarketType, budget_pct: float) -> float:
        if budget_pct <= 0:
            return 0.0
        if market_type == MarketType.perpetual:
            leverage = max(self.params.perpetual_leverage, 1)
            return budget_pct / leverage
        return budget_pct
