from fastapi import APIRouter, Query
from fastapi.responses import HTMLResponse, PlainTextResponse

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
        "last_cycle_at": payload["last_cycle_at"],
        "report_files": orchestrator.list_report_files()[:24],
        "strategy_meta": payload.get("strategy_meta", {}),
        "state": state.model_dump(mode="json"),
    }


@router.get("/api/reports/latest", response_class=PlainTextResponse)
async def latest_report() -> str:
    return orchestrator.latest_report_text()


@router.get("/api/reports", response_class=PlainTextResponse)
async def list_reports() -> str:
    files = orchestrator.list_report_files()
    if not files:
        return "暂无每小时报告"
    return "\n".join(files)


@router.get("/api/logs/tail", response_class=PlainTextResponse)
async def logs_tail(lines: int = Query(default=500, ge=100, le=5000)) -> str:
    return orchestrator.tail_runtime_log(lines=lines)


@router.get("/api/trades")
async def trades(limit: int = Query(default=500, ge=100, le=5000)) -> dict[str, object]:
    items = orchestrator.list_recent_trades(limit=limit)
    return {"count": len(items), "items": items}


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
    strategy_meta = payload.get("strategy_meta", {})
    assert isinstance(strategy_meta, dict)
    return render_dashboard(state, str(payload["message"]), str(payload["report"]), strategy_meta)
