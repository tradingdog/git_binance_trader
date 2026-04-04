from fastapi import APIRouter
from fastapi.responses import HTMLResponse

from git_binance_trader.core.models import DashboardState
from git_binance_trader.services.orchestrator import orchestrator
from git_binance_trader.web.dashboard import render_dashboard

router = APIRouter()


@router.get("/health")
async def health() -> dict[str, str | None]:
    payload = await orchestrator.dashboard()
    last_cycle_at = payload["last_cycle_at"]
    assert last_cycle_at is None or isinstance(last_cycle_at, str)
    return {
        "status": "ok",
        "mode": orchestrator.settings.trading_mode,
        "last_cycle_at": last_cycle_at,
    }


@router.get("/api/dashboard")
async def dashboard_data() -> dict[str, object]:
    payload = await orchestrator.dashboard()
    state = payload["state"]
    assert isinstance(state, DashboardState)
    return {
        "message": payload["message"],
        "report": payload["report"],
        "state": state.model_dump(mode="json"),
    }


@router.post("/api/actions/pause")
async def pause_trading() -> dict[str, str]:
    return await orchestrator.pause()


@router.post("/api/actions/resume")
async def resume_trading() -> dict[str, str]:
    return await orchestrator.resume()


@router.post("/api/actions/emergency-close")
async def emergency_close() -> dict[str, str]:
    return await orchestrator.emergency_close()


@router.get("/", response_class=HTMLResponse)
async def dashboard_page() -> str:
    payload = await orchestrator.dashboard()
    state = payload["state"]
    assert isinstance(state, DashboardState)
    return render_dashboard(state, str(payload["message"]), str(payload["report"]))
