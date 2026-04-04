from math import sqrt

from git_binance_trader.core.models import Position, Side, SymbolSnapshot, Trade


class OpportunityStrategy:
    name = "adaptive_opportunity_v1"

    def __init__(self) -> None:
        self.max_positions = 4
        self.max_exposure_pct = 25.0
        self.risk_per_trade_pct = 0.35

    def decide(
        self,
        *,
        watchlist: list[SymbolSnapshot],
        positions: dict[str, Position],
        cash: float,
        equity: float,
    ) -> tuple[list[Trade], str]:
        trades: list[Trade] = []
        insights: list[str] = []
        scored = self._score_candidates(watchlist)

        exits = self._build_rotation_exits(scored, positions)
        trades.extend(exits)
        if exits:
            insights.append(f"轮动退出 {len(exits)} 笔")

        exposure = self._current_exposure_pct(positions, equity)
        room = max(0.0, self.max_exposure_pct - exposure)
        slots = max(0, self.max_positions - len(positions))

        if slots == 0 or room <= 0:
            return trades, "; ".join(insights) if insights else "仓位已满，等待信号"

        for snapshot, score in scored:
            if snapshot.symbol in positions:
                continue
            if slots <= 0 or room <= 0:
                break
            if not self._entry_filter(snapshot):
                continue

            position_budget_pct = min(7.0, room / slots)
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
                    strategy=self.name,
                    note=note,
                )
            )
            insights.append(f"新开仓 {snapshot.symbol} score={score:.2f}")
            room -= position_budget_pct
            slots -= 1

        if not insights:
            insights.append("未发现满足条件的新机会")
        return trades, "; ".join(insights)

    def _score_candidates(self, watchlist: list[SymbolSnapshot]) -> list[tuple[SymbolSnapshot, float]]:
        candidates = [item for item in watchlist if item.market_cap_rank <= 300 and item.price > 0]
        scored: list[tuple[SymbolSnapshot, float]] = []
        for item in candidates:
            momentum = max(min(item.change_pct_24h, 12.0), -12.0)
            liquidity = sqrt(max(item.volume_24h, 1.0)) / 4000.0
            alpha_bonus = 0.8 if item.market_type.value == "alpha" else 0.0
            perp_bonus = 0.4 if item.market_type.value == "perpetual" else 0.0
            score = momentum * 0.62 + liquidity * 0.28 + alpha_bonus + perp_bonus
            scored.append((item, score))
        return sorted(scored, key=lambda row: row[1], reverse=True)

    def _entry_filter(self, snapshot: SymbolSnapshot) -> bool:
        return snapshot.change_pct_24h >= 0.6 and snapshot.volume_24h > 100000000

    def _build_rotation_exits(
        self,
        scored: list[tuple[SymbolSnapshot, float]],
        positions: dict[str, Position],
    ) -> list[Trade]:
        score_map = {item.symbol: score for item, score in scored}
        exits: list[Trade] = []
        for symbol, position in positions.items():
            score = score_map.get(symbol, -999.0)
            if score < -0.8:
                exits.append(
                    Trade(
                        symbol=symbol,
                        side=Side.sell,
                        quantity=position.quantity,
                        price=position.current_price,
                        market_type=position.market_type,
                        strategy=self.name,
                        note=f"机会衰减退出 score={score:.2f}",
                    )
                )
        return exits

    @staticmethod
    def _current_exposure_pct(positions: dict[str, Position], equity: float) -> float:
        if equity <= 0:
            return 0.0
        exposure = sum(position.market_value for position in positions.values())
        return exposure / equity * 100
