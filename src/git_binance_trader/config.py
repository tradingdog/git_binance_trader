import os
from functools import lru_cache
from pathlib import Path

from pydantic import BaseModel, Field

from dotenv import load_dotenv


load_dotenv()


class Settings(BaseModel):
    project_name: str = "git_binance_trader"
    trading_mode: str = Field(default="SIMULATION")
    initial_balance_usdt: float = 10000.0
    cycle_interval_seconds: int = 30
    persistent_data_dir: str = "data"
    reports_dir: str = "data/reports"
    logs_dir: str = "data/logs"
    equity_history_file: str = "data/history/equity-history.jsonl"
    report_interval_minutes: int = 60
    storage_min_free_mb: int = 1500
    storage_retention_days: int = 30
    storage_low_space_retention_days: int = 7
    max_drawdown_pct: float = 15.0
    max_daily_drawdown_pct: float = 5.0
    max_trade_loss_pct: float = 1.0
    top_symbols_limit: int = 1000
    default_perpetual_leverage: int = 3
    spot_maker_fee_rate: float = 0.00075
    spot_taker_fee_rate: float = 0.00075
    perpetual_maker_fee_rate: float = 0.00018
    perpetual_taker_fee_rate: float = 0.00045
    binance_api_key: str = Field(default="")
    binance_api_secret: str = Field(default="")
    fly_api_token: str = Field(default="")
    github_token: str = Field(default="")

    @property
    def simulation_only(self) -> bool:
        return self.trading_mode.upper() == "SIMULATION"

    @property
    def equity_history_path(self) -> str:
        return self.equity_history_file or str(Path(self.persistent_data_dir) / "history" / "equity-history.jsonl")


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    persistent_data_dir = os.getenv("PERSISTENT_DATA_DIR", "data")
    legacy_spot_fee_rate = os.getenv("SPOT_FEE_RATE")
    legacy_perpetual_fee_rate = os.getenv("PERPETUAL_FEE_RATE")
    return Settings(
        trading_mode=os.getenv("TRADING_MODE", "SIMULATION"),
        initial_balance_usdt=float(os.getenv("INITIAL_BALANCE_USDT", "10000")),
        cycle_interval_seconds=int(os.getenv("CYCLE_INTERVAL_SECONDS", "30")),
        persistent_data_dir=persistent_data_dir,
        reports_dir=os.getenv("REPORTS_DIR", str(Path(persistent_data_dir) / "reports")),
        logs_dir=os.getenv("LOGS_DIR", str(Path(persistent_data_dir) / "logs")),
        equity_history_file=os.getenv("EQUITY_HISTORY_FILE", str(Path(persistent_data_dir) / "history" / "equity-history.jsonl")),
        report_interval_minutes=int(os.getenv("REPORT_INTERVAL_MINUTES", "60")),
        storage_min_free_mb=int(os.getenv("STORAGE_MIN_FREE_MB", "1500")),
        storage_retention_days=int(os.getenv("STORAGE_RETENTION_DAYS", "30")),
        storage_low_space_retention_days=int(os.getenv("STORAGE_LOW_SPACE_RETENTION_DAYS", "7")),
        max_drawdown_pct=float(os.getenv("MAX_DRAWDOWN_PCT", "15")),
        max_daily_drawdown_pct=float(os.getenv("MAX_DAILY_DRAWDOWN_PCT", "5")),
        max_trade_loss_pct=float(os.getenv("MAX_TRADE_LOSS_PCT", "1")),
        top_symbols_limit=int(os.getenv("TOP_SYMBOLS_LIMIT", "1000")),
        default_perpetual_leverage=int(os.getenv("DEFAULT_PERPETUAL_LEVERAGE", "3")),
        spot_maker_fee_rate=float(os.getenv("SPOT_MAKER_FEE_RATE", legacy_spot_fee_rate or "0.00075")),
        spot_taker_fee_rate=float(os.getenv("SPOT_TAKER_FEE_RATE", legacy_spot_fee_rate or "0.00075")),
        perpetual_maker_fee_rate=float(
            os.getenv("PERPETUAL_MAKER_FEE_RATE", legacy_perpetual_fee_rate or "0.00018")
        ),
        perpetual_taker_fee_rate=float(
            os.getenv("PERPETUAL_TAKER_FEE_RATE", legacy_perpetual_fee_rate or "0.00045")
        ),
        binance_api_key=os.getenv("BINANCE_API_KEY", ""),
        binance_api_secret=os.getenv("BINANCE_API_SECRET", ""),
        fly_api_token=os.getenv("FLY_API_TOKEN", ""),
        github_token=os.getenv("GITHUB_TOKEN", ""),
    )
