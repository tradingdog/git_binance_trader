from __future__ import annotations

import os
from functools import lru_cache
from pathlib import Path

from dotenv import load_dotenv
from pydantic import BaseModel

load_dotenv()


class Settings(BaseModel):
    project_name: str = "git_binance_trader_ai"
    trading_mode: str = "SIMULATION"
    initial_balance_usdt: float = 10000.0
    cycle_interval_seconds: int = 5
    market_universe_limit: int = 300
    market_universe_refresh_ticks: int = 60
    # AI推理频率控制：每隔多少个tick才触发一次真实AI推理调用
    # 默认60 tick × 5s = 5分钟/次，相比每tick调用减少约60倍成本
    ai_call_every_n_ticks: int = 60
    ai_model_name: str = "gemini-2.5-pro"
    ai_input_price_per_million: float = 2.0
    ai_output_price_per_million: float = 12.0
    ai_cache_price_per_million: float = 0.2
    orchestration_backend: str = "embedded"
    ai_memory_file: str = "memory/ai-memory.jsonl"
    human_command_file: str = "memory/human-commands.jsonl"


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    project_root = Path(__file__).resolve().parents[2]
    ai_memory_file = os.getenv("AI_MEMORY_FILE", "memory/ai-memory.jsonl")
    human_command_file = os.getenv("HUMAN_COMMAND_FILE", "memory/human-commands.jsonl")
    ai_memory_path = Path(ai_memory_file)
    human_command_path = Path(human_command_file)
    if not ai_memory_path.is_absolute():
        ai_memory_path = project_root / ai_memory_path
    if not human_command_path.is_absolute():
        human_command_path = project_root / human_command_path
    return Settings(
        project_name=os.getenv("PROJECT_NAME", "git_binance_trader_ai"),
        trading_mode=os.getenv("TRADING_MODE", "SIMULATION"),
        initial_balance_usdt=float(os.getenv("INITIAL_BALANCE_USDT", "10000")),
        cycle_interval_seconds=int(os.getenv("CYCLE_INTERVAL_SECONDS", "5")),
        market_universe_limit=int(os.getenv("MARKET_UNIVERSE_LIMIT", "300")),
        market_universe_refresh_ticks=int(os.getenv("MARKET_UNIVERSE_REFRESH_TICKS", "60")),
        ai_call_every_n_ticks=int(os.getenv("AI_CALL_EVERY_N_TICKS", "60")),
        ai_model_name=os.getenv("AI_MODEL_NAME", "gemini-2.5-pro"),
        ai_input_price_per_million=float(os.getenv("AI_INPUT_PRICE_PER_MILLION", "2")),
        ai_output_price_per_million=float(os.getenv("AI_OUTPUT_PRICE_PER_MILLION", "12")),
        ai_cache_price_per_million=float(os.getenv("AI_CACHE_PRICE_PER_MILLION", "0.2")),
        orchestration_backend=os.getenv("ORCHESTRATION_BACKEND", "embedded"),
        ai_memory_file=str(ai_memory_path),
        human_command_file=str(human_command_path),
    )
