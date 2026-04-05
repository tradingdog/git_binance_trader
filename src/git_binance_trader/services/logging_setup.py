from __future__ import annotations

import logging
from logging.handlers import RotatingFileHandler
from pathlib import Path


def get_strategy_logger(logs_dir: str) -> logging.Logger:
    logger = logging.getLogger("strategy_runtime")
    if logger.handlers:
        return logger

    Path(logs_dir).mkdir(parents=True, exist_ok=True)
    log_path = Path(logs_dir) / "strategy.log"

    handler = RotatingFileHandler(log_path, maxBytes=1_500_000, backupCount=5, encoding="utf-8")
    handler.setFormatter(logging.Formatter("%(asctime)s | %(levelname)s | %(message)s"))

    logger.setLevel(logging.INFO)
    logger.addHandler(handler)
    logger.propagate = False
    return logger
