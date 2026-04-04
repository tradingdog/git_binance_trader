from pathlib import Path

import pytest

from git_binance_trader.config import Settings
from git_binance_trader.core.exchange import SimulationExchange
from git_binance_trader.core.risk import RiskManager
from git_binance_trader.services.orchestrator import TradingOrchestrator


@pytest.mark.anyio
async def test_run_cycle_generates_state_and_report(tmp_path: Path) -> None:
    orchestrator = TradingOrchestrator()
    orchestrator.settings = Settings(reports_dir=str(tmp_path), cycle_interval_seconds=1)
    orchestrator.risk_manager = RiskManager(orchestrator.settings)
    orchestrator.exchange = SimulationExchange(orchestrator.settings, orchestrator.risk_manager)

    state = await orchestrator.run_cycle()

    assert state.account.status.value in {"running", "paused", "halted"}
    reports = list(tmp_path.glob("report-*.md"))
    assert reports
    assert reports[0].read_text(encoding="utf-8").startswith("# 每小时策略报告")
