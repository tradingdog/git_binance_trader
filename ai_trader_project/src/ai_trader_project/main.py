from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.responses import HTMLResponse

from ai_trader_project.config import get_settings
from ai_trader_project.engine import GovernanceEngine
from ai_trader_project.models import (
    ActionRequest,
    ApprovalDecisionRequest,
    ConfigPatchRequest,
    HumanCommand,
    StructuredHumanCommand,
    TaskControlRequest,
)
from ai_trader_project.web.dashboard import render_dashboard

settings = get_settings()
engine = GovernanceEngine(settings)


@asynccontextmanager
async def lifespan(_: FastAPI):
    await engine.start()
    yield
    await engine.stop()


app = FastAPI(title=settings.project_name, lifespan=lifespan)


@app.get("/health")
async def health() -> dict[str, str | float | int]:
    state = await engine.snapshot()
    return {
        "status": "ok",
        "mode": settings.trading_mode,
        "engine_status": state.status.value,
        "equity": state.equity,
        "positions": state.positions,
    }


@app.get("/api/dashboard")
async def dashboard() -> dict[str, object]:
    return await engine.governance_payload()


@app.get("/api/ai/governance")
async def governance() -> dict[str, object]:
    return await engine.governance_payload()


@app.post("/api/ai/command")
async def submit_command(payload: HumanCommand) -> dict[str, object]:
    return await engine.record_command(operator=payload.operator, command=payload.command)


@app.post("/api/ai/command/structured")
async def submit_structured_command(payload: StructuredHumanCommand) -> dict[str, object]:
    return await engine.submit_structured_command(payload)


@app.post("/api/actions/pause")
async def pause(payload: ActionRequest | None = None) -> dict[str, str]:
    _ = payload
    return await engine.pause()


@app.post("/api/actions/resume")
async def resume(payload: ActionRequest | None = None) -> dict[str, str]:
    _ = payload
    return await engine.resume()


@app.post("/api/actions/emergency-close")
async def emergency_close(payload: ActionRequest | None = None) -> dict[str, str]:
    _ = payload
    return await engine.emergency_close()


@app.post("/api/actions/halt")
async def halt(payload: ActionRequest | None = None) -> dict[str, str]:
    _ = payload
    return await engine.halt()


@app.post("/api/actions/freeze-autonomy")
async def freeze_autonomy(payload: ActionRequest) -> dict[str, str]:
    return await engine.freeze_autonomy(payload)


@app.post("/api/actions/rollback")
async def rollback(payload: ActionRequest) -> dict[str, object]:
    return await engine.rollback(payload, reason="人工触发回滚")


@app.post("/api/governance/config")
async def patch_governance_config(payload: ConfigPatchRequest) -> dict[str, object]:
    return await engine.update_governance_config(payload)


@app.post("/api/governance/approvals/{approval_id}")
async def decide_approval(approval_id: str, payload: ApprovalDecisionRequest) -> dict[str, object]:
    return await engine.decide_approval(approval_id=approval_id, req=payload)


@app.post("/api/tasks/{task_id}/control")
async def control_task(task_id: str, payload: TaskControlRequest) -> dict[str, object]:
    return await engine.control_task(task_id=task_id, req=payload)


@app.get("/api/audit/replay")
async def audit_replay(limit: int = 80) -> dict[str, object]:
    return await engine.audit_replay(limit=limit)


@app.get("/api/governance/model-probe")
async def model_probe() -> dict[str, object]:
    return await engine.model_probe()


@app.get("/api/ai/code-proposals")
async def code_proposals() -> dict[str, object]:
    return await engine.list_code_proposals()


@app.get("/api/ai/code-versions")
async def code_versions() -> dict[str, object]:
    return await engine.list_code_versions()


@app.get("/api/market/timeseries")
async def market_timeseries(symbol: str = "", limit: int = 120) -> dict[str, object]:
    return await engine.market_timeseries(symbol=symbol, limit=limit)


@app.get("/", response_class=HTMLResponse)
async def page() -> str:
    return render_dashboard()
