from functools import lru_cache
from pydantic import BaseModel, Field
import os


class Settings(BaseModel):
    project_name: str = "git_binance_trader"
    trading_mode: str = Field(default="SIMULATION")
    initial_balance_usdt: float = 10000.0
    cycle_interval_seconds: int = 30
    reports_dir: str = "reports"
    max_drawdown_pct: float = 15.0
    max_daily_drawdown_pct: float = 5.0
    max_trade_loss_pct: float = 1.0
    top_symbols_limit: int = 300
    binance_api_key: str = Field(default="")
    binance_api_secret: str = Field(default="")
    fly_api_token: str = Field(default="")
    github_token: str = Field(default="")

    @property
    def simulation_only(self) -> bool:
        return self.trading_mode.upper() == "SIMULATION"


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings(
        trading_mode=os.getenv("TRADING_MODE", "SIMULATION"),
        initial_balance_usdt=float(os.getenv("INITIAL_BALANCE_USDT", "10000")),
        cycle_interval_seconds=int(os.getenv("CYCLE_INTERVAL_SECONDS", "30")),
        reports_dir=os.getenv("REPORTS_DIR", "reports"),
        max_drawdown_pct=float(os.getenv("MAX_DRAWDOWN_PCT", "15")),
        max_daily_drawdown_pct=float(os.getenv("MAX_DAILY_DRAWDOWN_PCT", "5")),
        max_trade_loss_pct=float(os.getenv("MAX_TRADE_LOSS_PCT", "1")),
        top_symbols_limit=int(os.getenv("TOP_SYMBOLS_LIMIT", "300")),
        binance_api_key=os.getenv("BINANCE_API_KEY", ""),
        binance_api_secret=os.getenv("BINANCE_API_SECRET", ""),
        fly_api_token=os.getenv("FLY_API_TOKEN", ""),
        github_token=os.getenv("GITHUB_TOKEN", ""),
    )
