from pathlib import Path

import pytest

from git_binance_trader.config import Settings
from git_binance_trader.core.exchange import SimulationExchange
from git_binance_trader.core.models import MarketType, Side, SymbolSnapshot, Trade
from git_binance_trader.core.risk import RiskManager
from git_binance_trader.services.history import EquityHistoryStore
from git_binance_trader.services.orchestrator import TradingOrchestrator


@pytest.mark.anyio
async def test_run_cycle_generates_state_and_report(tmp_path: Path) -> None:
    orchestrator = TradingOrchestrator()
    orchestrator.settings = Settings(
        persistent_data_dir=str(tmp_path / "data"),
        reports_dir=str(tmp_path / "reports"),
        logs_dir=str(tmp_path / "logs"),
        equity_history_file=str(tmp_path / "data" / "history" / "equity-history.jsonl"),
        cycle_interval_seconds=1,
    )
    orchestrator.risk_manager = RiskManager(orchestrator.settings)
    orchestrator.exchange = SimulationExchange(orchestrator.settings, orchestrator.risk_manager)
    orchestrator.history_store = EquityHistoryStore(orchestrator.settings)

    async def fake_top_symbols() -> list[SymbolSnapshot]:
        return [
            SymbolSnapshot(
                symbol="BTCUSDT",
                price=80000,
                market_cap_rank=1,
                volume_24h=30_000_000_000,
                change_pct_24h=2.0,
                market_type=MarketType.spot,
                leverage=1,
                data_source="binance-spot",
            )
        ]

    orchestrator.market_data.get_top_symbols = fake_top_symbols  # type: ignore[method-assign]

    state = await orchestrator.run_cycle()

    assert state.account.status.value in {"running", "paused", "halted"}
    reports = list((tmp_path / "reports").glob("report-*.md"))
    assert reports
    assert reports[0].read_text(encoding="utf-8").startswith("# 每小时策略报告")
    assert (tmp_path / "reports" / "strategy-compare.jsonl").exists()
    assert (tmp_path / "reports" / "strategy-compare-latest.md").exists()
    assert Path(orchestrator.settings.equity_history_path).exists()
    assert state.equity_history


def test_restore_exchange_state_keeps_accumulated_fees(tmp_path: Path) -> None:
    settings = Settings(
        persistent_data_dir=str(tmp_path / "data"),
        reports_dir=str(tmp_path / "reports"),
        logs_dir=str(tmp_path / "logs"),
        equity_history_file=str(tmp_path / "data" / "history" / "equity-history.jsonl"),
        exchange_state_file=str(tmp_path / "data" / "history" / "exchange-state.json"),
    )

    orchestrator = TradingOrchestrator()
    orchestrator.settings = settings
    orchestrator.risk_manager = RiskManager(settings)
    orchestrator.exchange = SimulationExchange(settings, orchestrator.risk_manager)
    orchestrator.history_store = EquityHistoryStore(settings)

    orchestrator.exchange.submit_trade(
        Trade(
            symbol="BTCUSDT",
            side=Side.buy,
            quantity=1,
            price=100,
            market_type=MarketType.spot,
            strategy="test",
        )
    )
    orchestrator.exchange.submit_trade(
        Trade(
            symbol="BTCUSDT",
            side=Side.sell,
            quantity=1,
            price=110,
            market_type=MarketType.spot,
            strategy="test",
        )
    )
    orchestrator.history_store.save_exchange_state(orchestrator.exchange.export_state())

    restored = SimulationExchange(settings, RiskManager(settings))
    orchestrator.exchange = restored
    orchestrator._restore_exchange_state()

    assert orchestrator.exchange.account_state()["fees_paid"] == 0.1575


def test_list_recent_trades_prefers_persisted_trade_history(tmp_path: Path) -> None:
    settings = Settings(
        persistent_data_dir=str(tmp_path / "data"),
        reports_dir=str(tmp_path / "reports"),
        logs_dir=str(tmp_path / "logs"),
        equity_history_file=str(tmp_path / "data" / "history" / "equity-history.jsonl"),
        exchange_state_file=str(tmp_path / "data" / "history" / "exchange-state.json"),
        trade_history_file=str(tmp_path / "data" / "history" / "trade-history.jsonl"),
    )

    orchestrator = TradingOrchestrator()
    orchestrator.settings = settings
    orchestrator.risk_manager = RiskManager(settings)
    orchestrator.exchange = SimulationExchange(settings, orchestrator.risk_manager)
    orchestrator.history_store = EquityHistoryStore(settings)

    first = Trade(
        symbol="BTCUSDT",
        side=Side.buy,
        quantity=1,
        price=100,
        market_type=MarketType.spot,
        strategy="test",
    )
    second = Trade(
        symbol="BTCUSDT",
        side=Side.sell,
        quantity=1,
        price=110,
        market_type=MarketType.spot,
        strategy="test",
    )
    orchestrator.exchange.trades = [first, second]
    orchestrator._sync_trade_history()
    orchestrator.exchange.trades = []

    items = orchestrator.list_recent_trades(limit=10)

    assert len(items) == 2
    assert items[0]["side"] == "sell"
    assert items[1]["side"] == "buy"
