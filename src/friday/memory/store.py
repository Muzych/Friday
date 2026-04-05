import json
from pathlib import Path
from urllib.parse import quote

from friday.memory.models import (
    DeepMemoryDelta,
    DeepMemorySnapshot,
    SessionMemoryDelta,
    SessionMemorySnapshot,
)


def _write_json(path: Path, payload: dict) -> None:
    path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def _safe_key(key: str) -> str:
    return quote(key, safe="")


class MemoryStore:
    def __init__(self, root: str | Path):
        self.root = Path(root)
        self.session_root = self.root / "session_memory"
        self.deep_root = self.root / "deep_memory"
        self.session_root.mkdir(parents=True, exist_ok=True)
        self.deep_root.mkdir(parents=True, exist_ok=True)

    def load_session_snapshot(self, session_id: str) -> SessionMemorySnapshot:
        path = self.session_root / f"{_safe_key(session_id)}.json"
        if not path.exists():
            return SessionMemorySnapshot(session_id=session_id)
        return SessionMemorySnapshot.model_validate_json(path.read_text(encoding="utf-8"))

    def load_deep_snapshot(self, actor_key: str) -> DeepMemorySnapshot:
        path = self.deep_root / f"{_safe_key(actor_key)}.json"
        if not path.exists():
            return DeepMemorySnapshot(actor_key=actor_key)
        return DeepMemorySnapshot.model_validate_json(path.read_text(encoding="utf-8"))

    def apply_session_delta(
        self,
        session_id: str,
        delta: SessionMemoryDelta,
    ) -> SessionMemorySnapshot:
        snapshot = self.load_session_snapshot(session_id)
        updated = snapshot.model_copy(
            update={
                "revision": snapshot.revision + 1,
                "summary": delta.summary or snapshot.summary,
                "goal": delta.goal or snapshot.goal,
                "active_tasks": list(delta.active_tasks),
                "constraints": list(delta.constraints),
                "open_questions": list(delta.open_questions),
                "recent_decisions": list(delta.recent_decisions),
                "follow_ups": list(delta.follow_ups),
            }
        )
        self.save_session_snapshot(updated)
        return updated

    def apply_deep_delta(
        self,
        actor_key: str,
        delta: DeepMemoryDelta,
    ) -> DeepMemorySnapshot:
        snapshot = self.load_deep_snapshot(actor_key)
        updated = snapshot.model_copy(
            update={
                "revision": snapshot.revision + 1,
                "profile_facts": list(delta.profile_facts),
                "preferences": list(delta.preferences),
                "long_running_projects": list(delta.long_running_projects),
                "stable_workflows": list(delta.stable_workflows),
            }
        )
        self.save_deep_snapshot(updated)
        return updated

    def save_session_snapshot(self, snapshot: SessionMemorySnapshot) -> None:
        _write_json(
            self.session_root / f"{_safe_key(snapshot.session_id)}.json",
            snapshot.model_dump(),
        )

    def save_deep_snapshot(self, snapshot: DeepMemorySnapshot) -> None:
        _write_json(
            self.deep_root / f"{_safe_key(snapshot.actor_key)}.json",
            snapshot.model_dump(),
        )
