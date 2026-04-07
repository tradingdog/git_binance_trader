from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

from ai_trader_project.config import Settings


class MemoryStore:
    def __init__(self, settings: Settings) -> None:
        self.ai_memory = Path(settings.ai_memory_file)
        self.command_memory = Path(settings.human_command_file)
        self.ai_memory.parent.mkdir(parents=True, exist_ok=True)
        self.command_memory.parent.mkdir(parents=True, exist_ok=True)
        if not self.ai_memory.exists():
            self.ai_memory.write_text("", encoding="utf-8")
        if not self.command_memory.exists():
            self.command_memory.write_text("", encoding="utf-8")

    def append_ai(self, event_type: str, actor: str, message: str, meta: dict[str, object] | None = None) -> None:
        payload = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "event_type": event_type,
            "actor": actor,
            "message": message,
            "meta": meta or {},
        }
        with self.ai_memory.open("a", encoding="utf-8") as f:
            f.write(json.dumps(payload, ensure_ascii=False) + "\n")

    def append_command(self, operator: str, command: str) -> dict[str, object]:
        payload = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "operator": operator,
            "command": command,
            "status": "recorded",
        }
        with self.command_memory.open("a", encoding="utf-8") as f:
            f.write(json.dumps(payload, ensure_ascii=False) + "\n")
        self.append_ai("human_command", operator, command, {"status": "recorded"})
        return payload

    def recent_ai(self, limit: int = 80) -> list[dict[str, object]]:
        rows = self.ai_memory.read_text(encoding="utf-8", errors="ignore").splitlines()
        out: list[dict[str, object]] = []
        for line in rows[-max(1, min(limit, 500)) :]:
            if not line.strip():
                continue
            try:
                obj = json.loads(line)
            except json.JSONDecodeError:
                continue
            if isinstance(obj, dict):
                out.append(obj)
        return list(reversed(out))

    def recent_commands(self, limit: int = 30) -> list[dict[str, object]]:
        rows = self.command_memory.read_text(encoding="utf-8", errors="ignore").splitlines()
        out: list[dict[str, object]] = []
        for line in rows[-max(1, min(limit, 200)) :]:
            if not line.strip():
                continue
            try:
                obj = json.loads(line)
            except json.JSONDecodeError:
                continue
            if isinstance(obj, dict):
                out.append(obj)
        return list(reversed(out))
