from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.responses import HTMLResponse

from ai_trader_project.config import get_settings
from ai_trader_project.engine import GovernanceEngine
from ai_trader_project.models import HumanCommand
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
async def health() -> dict[str, str]:
    state = await engine.snapshot()
    return {"status": "ok", "mode": settings.trading_mode, "engine_status": state.status}


@app.get("/api/dashboard")
async def dashboard() -> dict[str, object]:
    state = await engine.snapshot()
    return {
        "system": {
            "status": state.status,
            "equity": state.equity,
            "drawdown_pct": state.drawdown_pct,
            "daily_drawdown_pct": state.daily_drawdown_pct,
            "positions": state.positions,
            "ai_message": state.ai_message,
            "ai_insight": state.ai_insight,
            "generated_at": state.generated_at.isoformat(),
        }
    }


@app.get("/api/ai/governance")
async def governance() -> dict[str, object]:
    return await engine.governance_payload()


@app.post("/api/ai/command")
async def submit_command(payload: HumanCommand) -> dict[str, object]:
    return await engine.record_command(operator=payload.operator, command=payload.command)


@app.post("/api/actions/pause")
async def pause() -> dict[str, str]:
    return await engine.pause()


@app.post("/api/actions/resume")
async def resume() -> dict[str, str]:
    return await engine.resume()


@app.post("/api/actions/emergency-close")
async def emergency_close() -> dict[str, str]:
    return await engine.emergency_close()


@app.post("/api/actions/halt")
async def halt() -> dict[str, str]:
    return await engine.halt()


@app.get("/", response_class=HTMLResponse)
async def page() -> str:
    return render_dashboard()
