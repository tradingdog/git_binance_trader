from __future__ import annotations

import json
import shutil
from datetime import datetime, timedelta, timezone
from pathlib import Path

from git_binance_trader.config import Settings
from git_binance_trader.core.models import EquityPoint, StorageStatus


class EquityHistoryStore:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.base_dir = Path(settings.persistent_data_dir)
        self.history_path = Path(settings.equity_history_path)
        self.exchange_state_path = Path(settings.exchange_state_path)
        self.reports_dir = Path(settings.reports_dir)
        self.logs_dir = Path(settings.logs_dir)

    def append(self, point: EquityPoint) -> None:
        self.history_path.parent.mkdir(parents=True, exist_ok=True)
        with self.history_path.open("a", encoding="utf-8") as handle:
            handle.write(point.model_dump_json())
            handle.write("\n")

    def load(self, since: datetime | None = None) -> list[EquityPoint]:
        if not self.history_path.exists():
            return []

        points: list[EquityPoint] = []
        for raw_line in self.history_path.read_text(encoding="utf-8", errors="ignore").splitlines():
            if not raw_line.strip():
                continue
            try:
                payload = json.loads(raw_line)
                point = EquityPoint.model_validate(payload)
            except Exception:
                continue
            if since is None or point.timestamp >= since:
                points.append(point)
        return points

    def save_exchange_state(self, payload: dict[str, object]) -> None:
        self.exchange_state_path.parent.mkdir(parents=True, exist_ok=True)
        temp_path = self.exchange_state_path.with_suffix(".tmp")
        temp_path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
        temp_path.replace(self.exchange_state_path)

    def load_exchange_state(self) -> dict[str, object] | None:
        if not self.exchange_state_path.exists():
            return None
        try:
            payload = json.loads(self.exchange_state_path.read_text(encoding="utf-8", errors="ignore"))
        except Exception:
            return None
        if not isinstance(payload, dict):
            return None
        return payload

    def ensure_headroom(self) -> None:
        status = self.storage_status()
        if status.free_mb >= self.settings.storage_min_free_mb:
            return

        self._prune_history(days=self.settings.storage_low_space_retention_days)
        self._prune_reports(days=self.settings.storage_low_space_retention_days)
        self._prune_logs(keep_files=2)

    def storage_status(self) -> StorageStatus:
        inspect_path = self.base_dir
        inspect_path.mkdir(parents=True, exist_ok=True)
        usage = shutil.disk_usage(inspect_path)
        total_mb = round(usage.total / 1024 / 1024, 2)
        free_mb = round(usage.free / 1024 / 1024, 2)
        return StorageStatus(
            path=str(inspect_path),
            total_mb=total_mb,
            free_mb=free_mb,
            min_free_mb=self.settings.storage_min_free_mb,
            cleanup_required=free_mb < self.settings.storage_min_free_mb,
        )

    def _prune_history(self, days: int) -> None:
        if not self.history_path.exists():
            return

        cutoff = datetime.now(timezone.utc) - timedelta(days=days)
        retained = [point.model_dump_json() for point in self.load(since=cutoff)]
        self.history_path.parent.mkdir(parents=True, exist_ok=True)
        content = "\n".join(retained)
        if content:
            content += "\n"
        self.history_path.write_text(content, encoding="utf-8")

    def _prune_reports(self, days: int) -> None:
        if not self.reports_dir.exists():
            return

        cutoff = datetime.now(timezone.utc) - timedelta(days=days)
        for path in self.reports_dir.glob("report-*.md"):
            modified_at = datetime.fromtimestamp(path.stat().st_mtime, tz=timezone.utc)
            if modified_at < cutoff:
                path.unlink(missing_ok=True)

    def _prune_logs(self, keep_files: int) -> None:
        if not self.logs_dir.exists():
            return

        candidates = sorted(
            self.logs_dir.glob("strategy.log*"),
            key=lambda path: path.stat().st_mtime,
            reverse=True,
        )
        for path in candidates[keep_files:]:
            path.unlink(missing_ok=True)
