from __future__ import annotations

from datetime import datetime, timezone
from math import log10
import re

from git_binance_trader.config import Settings
from git_binance_trader.core.models import LiquidityType, MarketType, Position, Side, StrategyState, SymbolSnapshot, Trade
from git_binance_trader.core.risk import RiskManager


class SimulationExchange:
    def __init__(self, settings: Settings, risk_manager: RiskManager) -> None:
        self.settings = settings
        self.risk_manager = risk_manager
        self.cash = settings.initial_balance_usdt
        self.realized_pnl = 0.0
        self.total_fees = 0.0
        self.total_funding_paid = 0.0
        self.positions: dict[str, Position] = {}
        self.trades: list[Trade] = []
        self.peak_equity = settings.initial_balance_usdt
        self.start_of_day_equity = settings.initial_balance_usdt
        self.status = StrategyState.running
        self.last_message = "系统已初始化"
        self._latest_snapshot_map: dict[str, SymbolSnapshot] = {}

    def apply_market_prices(self, watchlist: list[SymbolSnapshot], now_ts_ms: int | None = None) -> None:
        snapshot_map = {self._position_key(item.symbol, item.market_type): item for item in watchlist}
        self._latest_snapshot_map = dict(snapshot_map)
        now_ms = now_ts_ms if now_ts_ms is not None else int(datetime.now(timezone.utc).timestamp() * 1000)
        to_close: list[Trade] = []
        for position in self.positions.values():
            position_key = self._position_key(position.symbol, position.market_type)
            if position_key in snapshot_map:
                snapshot = snapshot_map[position_key]
                position.current_price = snapshot.price
                if position.market_type == MarketType.perpetual:
                    position.current_funding_rate = snapshot.funding_rate
                    if snapshot.funding_interval_hours > 0:
                        position.funding_interval_hours = snapshot.funding_interval_hours
                    if snapshot.next_funding_time_ms > 0:
                        position.next_funding_time_ms = snapshot.next_funding_time_ms
                    self._apply_funding_if_due(position, now_ms)
                if position.current_price > position.highest_price:
                    position.highest_price = position.current_price
                    trailing_stop = position.highest_price * (1 - position.trailing_stop_gap_pct / 100)
                    if trailing_stop > position.stop_loss:
                        position.stop_loss = trailing_stop
                if position.current_price <= position.stop_loss:
                    to_close.append(
                        Trade(
                            symbol=position.symbol,
                            side=Side.sell,
                            quantity=position.quantity,
                            price=position.current_price,
                            market_type=position.market_type,
                            strategy="risk_guard",
                            note="触发止损/跟踪止盈",
                        )
                    )
                elif position.current_price >= position.take_profit:
                    to_close.append(
                        Trade(
                            symbol=position.symbol,
                            side=Side.sell,
                            quantity=position.quantity,
                            price=position.current_price,
                            market_type=position.market_type,
                            strategy="risk_guard",
                            note="触发止盈",
                        )
                    )

        for trade in to_close:
            position_key = self._position_key(trade.symbol, trade.market_type)
            if position_key in self.positions:
                self.submit_trade(trade)

    def submit_trade(self, trade: Trade) -> None:
        if not self.settings.simulation_only:
            raise RuntimeError("仅允许模拟盘运行")
        position_key = self._position_key(trade.symbol, trade.market_type)
        if position_key not in self.positions and trade.side == Side.sell:
            self.last_message = f"忽略无持仓卖出: {trade.symbol}"
            return

        leverage = max(trade.leverage, 1)
        notional = trade.quantity * trade.price
        liquidity_type = self._effective_liquidity_type(trade)
        trade.liquidity_type = liquidity_type
        fee_paid = notional * self._fee_rate(trade.market_type, liquidity_type)
        margin_required = notional / leverage if trade.market_type == MarketType.perpetual else notional
        if trade.side == Side.buy:
            if self.cash < margin_required + fee_paid:
                self.last_message = f"资金不足，忽略买单: {trade.symbol}"
                return
            self.cash -= margin_required + fee_paid
            trade.fee_paid = fee_paid
            self.total_fees += fee_paid
            snapshot = self._latest_snapshot_map.get(position_key)
            stop_loss, take_profit, take_profit_pct, trailing_gap_pct = self._dynamic_exit_levels(trade, snapshot)
            self.positions[position_key] = Position(
                symbol=trade.symbol,
                quantity=trade.quantity,
                entry_price=trade.price,
                current_price=trade.price,
                market_type=trade.market_type,
                side=trade.side,
                leverage=leverage,
                stop_loss=stop_loss,
                take_profit=take_profit,
                take_profit_pct=take_profit_pct,
                trailing_stop_gap_pct=trailing_gap_pct,
                highest_price=trade.price,
                entry_fee=fee_paid,
                funding_interval_hours=8,
            )
            self.trades.append(trade)
            self.last_message = f"已模拟开仓: {trade.symbol}"
            return

        position = self.positions[position_key]
        gross_realized_pnl = (trade.price - position.entry_price) * position.quantity
        realized_pnl = gross_realized_pnl - position.entry_fee - fee_paid
        trade.realized_pnl = realized_pnl
        trade.fee_paid = fee_paid
        trade.leverage = position.leverage
        self.realized_pnl += realized_pnl
        self.total_fees += fee_paid
        released_margin = position.margin_used
        if trade.market_type == MarketType.perpetual:
            self.cash += released_margin + gross_realized_pnl - fee_paid
        else:
            self.cash += trade.quantity * trade.price - fee_paid
        del self.positions[position_key]
        self.trades.append(trade)
        self.last_message = f"已模拟平仓: {trade.symbol}"

    def account_state(self) -> dict[str, float]:
        unrealized_pnl = sum(position.unrealized_pnl for position in self.positions.values())
        position_value = sum(position.market_value for position in self.positions.values())
        margin_value = sum(position.margin_used for position in self.positions.values())
        equity = self.cash + margin_value + unrealized_pnl
        self.peak_equity = max(self.peak_equity, equity)
        total_return_pct = (equity - self.settings.initial_balance_usdt) / self.settings.initial_balance_usdt * 100
        drawdown_pct = max(0.0, (self.peak_equity - equity) / self.peak_equity * 100) if self.peak_equity else 0.0
        single_trade_loss_pct = 0.0
        if self.trades:
            worst_trade = min((trade.realized_pnl for trade in self.trades), default=0.0)
            single_trade_loss_pct = abs(min(worst_trade, 0.0)) / self.settings.initial_balance_usdt * 100
        daily_drawdown_pct = max(0.0, (self.start_of_day_equity - equity) / self.start_of_day_equity * 100)
        return {
            "equity": round(equity, 4),
            "cash": round(self.cash, 4),
            "margin_used": round(margin_value, 4),
            "position_value": round(position_value, 4),
            "balance_check_delta": round(equity - self.cash - margin_value - unrealized_pnl, 8),
            "unrealized_pnl": round(unrealized_pnl, 4),
            "realized_pnl": round(self.realized_pnl, 4),
            "fees_paid": round(self.total_fees, 4),
            "funding_paid": round(self.total_funding_paid, 4),
            "total_return_pct": round(total_return_pct, 4),
            "drawdown_pct": round(drawdown_pct, 4),
            "daily_drawdown_pct": round(daily_drawdown_pct, 4),
            "single_trade_loss_pct": round(single_trade_loss_pct, 4),
        }

    def evaluate_risk(self) -> tuple[bool, str, dict[str, float]]:
        metrics = self.account_state()
        risk_status = self.risk_manager.evaluate(
            peak_equity=self.peak_equity,
            current_equity=metrics["equity"],
            start_of_day_equity=self.start_of_day_equity,
            single_trade_loss_pct=metrics["single_trade_loss_pct"],
        )
        if risk_status.breached:
            self.status = StrategyState.halted
            self.close_all_positions(reason=risk_status.message)
        return risk_status.breached, risk_status.message, metrics

    def pause(self) -> None:
        self.status = StrategyState.paused
        self.last_message = "交易已暂停"

    def resume(self) -> None:
        self.status = StrategyState.running
        self.last_message = "交易已恢复"

    def close_all_positions(self, reason: str) -> None:
        for position_key in list(self.positions.keys()):
            position = self.positions[position_key]
            self.submit_trade(
                Trade(
                    symbol=position.symbol,
                    side=Side.sell,
                    quantity=position.quantity,
                    price=position.current_price,
                    realized_pnl=position.unrealized_pnl,
                    market_type=position.market_type,
                    strategy="risk_guard",
                    note=reason,
                )
            )
        self.last_message = f"已执行紧急平仓: {reason}"

    @staticmethod
    def _position_key(symbol: str, market_type) -> str:
        return f"{market_type.value}:{symbol}"

    @staticmethod
    def _effective_liquidity_type(trade: Trade) -> LiquidityType:
        if trade.liquidity_type != LiquidityType.auto:
            return trade.liquidity_type
        if trade.strategy == "risk_guard":
            return LiquidityType.taker
        return LiquidityType.maker

    def _fee_rate(self, market_type: MarketType, liquidity_type: LiquidityType) -> float:
        # Alpha 分类币种复用现货双费率设置。
        if market_type == MarketType.perpetual:
            if liquidity_type == LiquidityType.taker:
                return max(self.settings.perpetual_taker_fee_rate, 0.0)
            return max(self.settings.perpetual_maker_fee_rate, 0.0)
        if liquidity_type == LiquidityType.taker:
            return max(self.settings.spot_taker_fee_rate, 0.0)
        return max(self.settings.spot_maker_fee_rate, 0.0)

    def _apply_funding_if_due(self, position: Position, now_ts_ms: int) -> None:
        if position.market_type != MarketType.perpetual:
            return
        next_funding_time_ms = position.next_funding_time_ms
        if next_funding_time_ms <= 0:
            return
        interval_hours = max(position.funding_interval_hours, 1)
        interval_ms = interval_hours * 60 * 60 * 1000

        while now_ts_ms >= next_funding_time_ms and position.last_funding_apply_time_ms < next_funding_time_ms:
            # 当前系统只模拟单向多头：正 fundingRate 代表支付，负 fundingRate 代表收取。
            funding_payment = position.market_value * position.current_funding_rate
            self.cash -= funding_payment
            self.realized_pnl -= funding_payment
            self.total_funding_paid += funding_payment
            position.last_funding_apply_time_ms = next_funding_time_ms
            next_funding_time_ms += interval_ms

        position.next_funding_time_ms = next_funding_time_ms

    def _dynamic_exit_levels(
        self,
        trade: Trade,
        snapshot: SymbolSnapshot | None,
    ) -> tuple[float, float, float, float]:
        base_tp_by_market = {
            MarketType.spot: 1.8,
            MarketType.perpetual: 2.4,
            MarketType.alpha: 3.2,
        }
        base_sl_by_market = {
            MarketType.spot: 0.9,
            MarketType.perpetual: 1.0,
            MarketType.alpha: 1.2,
        }
        base_trail_by_market = {
            MarketType.spot: 0.8,
            MarketType.perpetual: 1.0,
            MarketType.alpha: 1.15,
        }

        base_tp = base_tp_by_market.get(trade.market_type, 1.8)
        base_sl = base_sl_by_market.get(trade.market_type, 0.9)
        base_trail = base_trail_by_market.get(trade.market_type, 0.8)

        score = self._extract_score_from_note(trade.note)
        score_bonus = 0.0
        if score is not None:
            score_bonus = max(min((score - 3.0) * 0.24, 1.9), -0.8)

        momentum_bonus = 0.0
        volume_bonus = 0.0
        funding_penalty = 0.0
        if snapshot is not None:
            momentum_bonus = max(min(snapshot.change_pct_24h, 18.0), 0.0) / 18.0 * 1.8
            volume_bonus = max(min(log10(max(snapshot.volume_24h, 1.0) / 100_000_000.0 + 1.0), 1.2), 0.0)
            if trade.market_type == MarketType.perpetual:
                funding_penalty = max(snapshot.funding_rate, 0.0) * 12000

        tp_pct = base_tp + score_bonus + momentum_bonus + volume_bonus - funding_penalty
        if score is not None and score < 2.2:
            tp_pct -= 0.5
        tp_pct = max(min(tp_pct, 8.8 if trade.market_type == MarketType.alpha else 7.2), 1.2)

        sl_pct = max(min(tp_pct * 0.46, 2.2), base_sl)
        trail_gap_pct = max(min(tp_pct * 0.36, 2.4), base_trail)

        stop_loss = trade.price * (1 - sl_pct / 100)
        take_profit = trade.price * (1 + tp_pct / 100)
        return stop_loss, take_profit, round(tp_pct, 4), round(trail_gap_pct, 4)

    @staticmethod
    def _extract_score_from_note(note: str) -> float | None:
        if not note:
            return None
        match = re.search(r"score=([-+]?\d+(?:\.\d+)?)", note)
        if not match:
            return None
        try:
            return float(match.group(1))
        except ValueError:
            return None
