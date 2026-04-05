from contextlib import asynccontextmanager

from fastapi import FastAPI

from git_binance_trader.api.routes import router
from git_binance_trader.config import get_settings
from git_binance_trader.services.orchestrator import orchestrator

settings = get_settings()


@asynccontextmanager
async def lifespan(_: FastAPI):
	await orchestrator.start()
	yield
	await orchestrator.stop()


app = FastAPI(title=settings.project_name, lifespan=lifespan)
app.include_router(router)
