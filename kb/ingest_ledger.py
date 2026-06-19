from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from pathlib import Path
import json
from typing import Any


STATE_VERSION = 1


def now_iso() -> str:
    return datetime.now(UTC).isoformat(timespec="seconds").replace("+00:00", "Z")


@dataclass(frozen=True)
class IngestLedgerKey:
    dataset: str
    session_id: str | None
    source: str
    source_id: str
    content_hash: str

    def stable_id(self) -> str:
        return "|".join(
            [
                self.dataset,
                self.session_id or "",
                self.source,
                self.source_id,
                self.content_hash,
            ]
        )


class IngestLedger:
    """Small JSON ledger for source revisions already handed to Cognee."""

    def __init__(self, path: str | Path | None) -> None:
        self.path = Path(path) if path else None

    @property
    def enabled(self) -> bool:
        return self.path is not None

    def contains(self, key: IngestLedgerKey) -> bool:
        if not self.path:
            return False
        return key.stable_id() in self._load().get("entries", {})

    def record(
        self,
        key: IngestLedgerKey,
        *,
        metadata: dict[str, Any],
        tags: tuple[str, ...],
    ) -> None:
        if not self.path:
            return
        state = self._load()
        entries = state.setdefault("entries", {})
        entries[key.stable_id()] = {
            **asdict(key),
            "recorded_at": now_iso(),
            "metadata": metadata,
            "tags": list(tags),
        }
        state["version"] = STATE_VERSION
        self._save(state)

    def _load(self) -> dict[str, Any]:
        if not self.path or not self.path.exists():
            return {"version": STATE_VERSION, "entries": {}}
        try:
            data = json.loads(self.path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return {"version": STATE_VERSION, "entries": {}}
        if not isinstance(data, dict):
            return {"version": STATE_VERSION, "entries": {}}
        entries = data.get("entries")
        if not isinstance(entries, dict):
            entries = {}
        return {"version": data.get("version", STATE_VERSION), "entries": entries}

    def _save(self, state: dict[str, Any]) -> None:
        if not self.path:
            return
        self.path.parent.mkdir(parents=True, exist_ok=True)
        temp_path = self.path.with_suffix(f"{self.path.suffix}.tmp")
        temp_path.write_text(json.dumps(state, indent=2, sort_keys=True), encoding="utf-8")
        temp_path.replace(self.path)
