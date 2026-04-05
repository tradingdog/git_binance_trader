from __future__ import annotations

from collections import defaultdict, deque
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from math import log10, sqrt

from git_binance_trader.core.models import LiquidityType, MarketType, Position, Side, SymbolSnapshot, Trade


@dataclass
class AdaptiveParams:
    max_positions: int = 4
    max_exposure_pct: float = 25.0
    entry_score_threshold: float = 2.8
    rotation_exit_score: float = 1.6
    position_budget_pct: float = 6.0
    min_quote_volume: float = 120_000_000.0
    perpetual_leverage: int = 3


class OpportunityStrategy:
    name = "adaptive_opportunity_v2"

    def __init__(self) -> None:
        self.risk_per_trade_pct = 0.35
        self.params = AdaptiveParams()
        self._series: dict[str, deque[tuple[float, float, float]]] = defaultdict(lambda: deque(maxlen=90))
        self._first_seen_ts: dict[str, datetime] = {}
        self._last_adapt_hour: str | None = None
        self._last_adaptation_event: dict[str, object] | None = None

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
        scored = self._score_candidates(watchlist, now)

        exits = self._build_rotation_exits(scored, positions)
        trades.extend(exits)
        if exits:
            insights.append(f"轮动退出 {len(exits)} 笔")

        exposure = self._current_exposure_pct(positions, equity)
        room = max(0.0, self.params.max_exposure_pct - exposure)
        slots = max(0, self.params.max_positions - len(positions))

        if slots == 0 or room <= 0:
            return trades, "; ".join(insights) if insights else "仓位已满，等待信号"

        for snapshot, score in scored:
            if any(
                position.symbol == snapshot.symbol and position.market_type == snapshot.market_type
                for position in positions.values()
            ):
                continue
            if slots <= 0 or room <= 0:
                break
            if score < self.params.entry_score_threshold:
                continue
            if snapshot.volume_24h < self.params.min_quote_volume:
                continue

            position_budget_pct = min(self.params.position_budget_pct, room / slots)
            notional = equity * position_budget_pct / 100
            notional = min(notional, cash)
            if notional <= 20:
                break

            quantity = round(notional / snapshot.price, 6)
            if quantity <= 0:
                continue

            note = f"机会开仓 score={score:.2f} risk={self.risk_per_trade_pct:.2f}%"
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
            insights.append(f"新开仓 {snapshot.symbol} score={score:.2f} model={snapshot.market_type.value}")
            room -= position_budget_pct
            slots -= 1

        if not insights:
            insights.append("未发现满足条件的新机会")
        return trades, "; ".join(insights)

    def _score_candidates(self, watchlist: list[SymbolSnapshot], now: datetime | None = None) -> list[tuple[SymbolSnapshot, float]]:
        now_ts = now or datetime.now(timezone.utc)
        candidates = [item for item in watchlist if item.price > 0]
        best_by_symbol: dict[str, tuple[SymbolSnapshot, float]] = {}
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
            existing = best_by_symbol.get(item.symbol)
            if existing is None or score > existing[1]:
                best_by_symbol[item.symbol] = (item, score)
        return sorted(best_by_symbol.values(), key=lambda row: row[1], reverse=True)

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
        if len(recent_prices) >= 6:
            hi = max(recent_prices)
            lo = min(recent_prices)
            spread_pct = (hi - lo) / max(snapshot.price, 1e-9)
            squeeze_score = max(0.0, 0.06 - spread_pct) / 0.06
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

        return {
            "momentum": momentum,
            "volume_surge": volume_surge,
            "volatility_breakout": volatility_breakout,
            "cross_market_strength": cross_market_strength,
            "social_heat": social_heat,
            "new_coin_behavior": new_coin_behavior,
            "liquidity": sqrt(max(snapshot.volume_24h, 1.0)) / 10000.0,
        }

    @staticmethod
    def _score_spot(f: dict[str, float]) -> float:
        return (
            f["momentum"] * 1.4
            + f["volume_surge"] * 1.1
            + f["volatility_breakout"] * 1.0
            + f["cross_market_strength"] * 0.8
            + f["social_heat"] * 0.5
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
            + f["liquidity"] * 0.7
        )

    def _build_rotation_exits(
        self,
        scored: list[tuple[SymbolSnapshot, float]],
        positions: dict[str, Position],
    ) -> list[Trade]:
        score_map = {f"{item.market_type.value}:{item.symbol}": score for item, score in scored}
        exits: list[Trade] = []
        for position in positions.values():
            score = score_map.get(f"{position.market_type.value}:{position.symbol}", -999.0)
            if score < self.params.rotation_exit_score:
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
                        note=f"机会衰减退出 score={score:.2f}",
                    )
                )
        return exits

    def _ingest_watchlist(self, watchlist: list[SymbolSnapshot], now: datetime) -> None:
        for item in watchlist:
            key = f"{item.market_type.value}:{item.symbol}"
            self._series[key].append((item.price, max(item.volume_24h, 1.0), item.change_pct_24h))
            self._first_seen_ts.setdefault(key, now)

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
        win_rate = len(wins) / len(closed) if closed else 0.5
        avg_pnl = realized_sum / len(closed) if closed else 0.0

        if closed and (win_rate < 0.45 or avg_pnl < 0):
            self.params.max_positions = max(2, self.params.max_positions - 1)
            self.params.max_exposure_pct = max(14.0, self.params.max_exposure_pct - 3.0)
            self.params.entry_score_threshold = min(4.8, self.params.entry_score_threshold + 0.35)
            self.params.rotation_exit_score = min(2.6, self.params.rotation_exit_score + 0.2)
            self.params.position_budget_pct = max(3.6, self.params.position_budget_pct - 0.5)
            self.params.min_quote_volume = min(320_000_000.0, self.params.min_quote_volume * 1.08)
        elif closed and (win_rate > 0.6 and avg_pnl > 0):
            self.params.max_positions = min(5, self.params.max_positions + 1)
            self.params.max_exposure_pct = min(30.0, self.params.max_exposure_pct + 2.0)
            self.params.entry_score_threshold = max(2.2, self.params.entry_score_threshold - 0.2)
            self.params.rotation_exit_score = max(1.2, self.params.rotation_exit_score - 0.1)
            self.params.position_budget_pct = min(7.0, self.params.position_budget_pct + 0.3)
            self.params.min_quote_volume = max(80_000_000.0, self.params.min_quote_volume * 0.96)

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
            },
        }

    def get_and_clear_adaptation_event(self) -> dict[str, object] | None:
        event = self._last_adaptation_event
        self._last_adaptation_event = None
        return event

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
