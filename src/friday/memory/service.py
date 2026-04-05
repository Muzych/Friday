import hashlib
from pathlib import Path

from republic import LLM, RepublicError, TapeContext, TapeEntry
from republic.tape import AsyncTapeStore, TapeStore

from friday.memory.extractor import MemoryExtractor
from friday.memory.models import (
    DeepMemoryDelta,
    DeepMemorySnapshot,
    MemoryUpdateResult,
    RenderableMemoryContext,
    SessionMemoryDelta,
    SessionMemorySnapshot,
)
from friday.memory.prompting import render_memory_blocks
from friday.memory.store import MemoryStore


class MemoryService:
    def __init__(
        self,
        *,
        root: str | Path,
        workspace: str | Path,
        llm: LLM,
        extractor: MemoryExtractor,
        chunk_size: int = 25,
    ) -> None:
        self.root = Path(root)
        self.workspace = Path(workspace)
        self.store = MemoryStore(self.root)
        self.llm = llm
        self.extractor = extractor
        self.chunk_size = chunk_size

    @classmethod
    def from_runtime(
        cls,
        *,
        root: str | Path,
        workspace: str | Path,
        model: str,
        api_key: str | dict[str, str] | None,
        api_base: str | dict[str, str] | None,
        api_format: str,
        tape_store: TapeStore | AsyncTapeStore,
        context: TapeContext | None = None,
    ) -> "MemoryService":
        llm = LLM(
            model=model,
            api_key=api_key,
            api_base=api_base,
            api_format=api_format,
            tape_store=tape_store,
            context=context,
        )
        return cls(root=root, workspace=workspace, llm=llm, extractor=MemoryExtractor(llm))

    def tape_for_session(self, session_id: str):
        workspace_hash = hashlib.md5(
            str(self.workspace.resolve()).encode("utf-8"),
            usedforsecurity=False,
        ).hexdigest()[:16]
        session_hash = hashlib.md5(
            session_id.encode("utf-8"),
            usedforsecurity=False,
        ).hexdigest()[:16]
        return self.llm.tape(f"{workspace_hash}__{session_hash}")

    async def load_context(
        self,
        *,
        session_id: str,
        actor_key: str | None,
    ) -> RenderableMemoryContext:
        session_snapshot = self.store.load_session_snapshot(session_id)
        deep_snapshot = self.store.load_deep_snapshot(actor_key) if actor_key else None
        rendered_prompt = render_memory_blocks(session_snapshot, deep_snapshot)
        return RenderableMemoryContext(
            session_snapshot=session_snapshot,
            deep_snapshot=deep_snapshot,
            rendered_prompt=rendered_prompt,
        )

    def get_session_snapshot(self, session_id: str) -> SessionMemorySnapshot:
        return self.store.load_session_snapshot(session_id)

    def get_deep_snapshot(self, actor_key: str) -> DeepMemorySnapshot:
        return self.store.load_deep_snapshot(actor_key)

    async def update_memories(
        self,
        *,
        session_id: str,
        actor_key: str | None,
    ) -> MemoryUpdateResult:
        tape = self.tape_for_session(session_id)
        session_entries = await self._entries_since_anchor(
            tape=tape,
            anchor_name="session_memory/snapshot",
        )

        session_snapshot = self.store.load_session_snapshot(session_id)
        if session_entries:
            session_snapshot = await self._apply_session_entries(
                session_id=session_id,
                entries=session_entries,
                initial_snapshot=session_snapshot,
            )
            session_anchor = await self._append_anchor(
                tape=tape,
                name="session_memory/snapshot",
                state={"session_id": session_id, "revision": session_snapshot.revision},
            )
            session_snapshot = session_snapshot.model_copy(update={"last_anchor_id": str(session_anchor.id)})
            self.store.save_session_snapshot(session_snapshot)

        deep_snapshot: DeepMemorySnapshot | None = None
        if actor_key:
            deep_entries = await self._entries_since_anchor(
                tape=tape,
                anchor_name="deep_memory/snapshot",
            )
            deep_snapshot = self.store.load_deep_snapshot(actor_key)
            if deep_entries:
                deep_delta = await self.extractor.extract_deep_delta(
                    entries=deep_entries,
                    session_snapshot=session_snapshot,
                    snapshot=deep_snapshot,
                )
                deep_snapshot = self.store.apply_deep_delta(actor_key, deep_delta)
                deep_anchor = await self._append_anchor(
                    tape=tape,
                    name="deep_memory/snapshot",
                    state={"actor_key": actor_key, "revision": deep_snapshot.revision},
                )
                deep_snapshot = deep_snapshot.model_copy(update={"last_anchor_id": str(deep_anchor.id)})
                self.store.save_deep_snapshot(deep_snapshot)

        return MemoryUpdateResult(
            session_snapshot=session_snapshot,
            deep_snapshot=deep_snapshot,
            processed_entry_count=len(session_entries),
        )

    async def rebuild_session_memory(
        self,
        *,
        session_id: str,
        actor_key: str | None = None,
    ) -> MemoryUpdateResult:
        tape = self.tape_for_session(session_id)
        entries = list(
            await tape.query_async.kinds("message").all()
        )
        session_snapshot = SessionMemorySnapshot(session_id=session_id)
        if entries:
            session_snapshot = await self._rebuild_session_from_entries(
                session_id=session_id,
                entries=entries,
                initial_snapshot=session_snapshot,
            )
            session_anchor = await self._append_anchor(
                tape=tape,
                name="session_memory/snapshot",
                state={"session_id": session_id, "revision": session_snapshot.revision, "rebuild": True},
            )
            session_snapshot = session_snapshot.model_copy(update={"last_anchor_id": str(session_anchor.id)})
        self.store.save_session_snapshot(session_snapshot)

        deep_snapshot: DeepMemorySnapshot | None = None
        if actor_key:
            deep_snapshot = DeepMemorySnapshot(actor_key=actor_key)
            if entries:
                deep_delta = await self.extractor.extract_deep_delta(
                    entries=entries,
                    session_snapshot=session_snapshot,
                    snapshot=deep_snapshot,
                )
                deep_snapshot = self._merge_deep_snapshot(deep_snapshot, deep_delta)
                deep_anchor = await self._append_anchor(
                    tape=tape,
                    name="deep_memory/snapshot",
                    state={"actor_key": actor_key, "revision": deep_snapshot.revision, "rebuild": True},
                )
                deep_snapshot = deep_snapshot.model_copy(update={"last_anchor_id": str(deep_anchor.id)})
            self.store.save_deep_snapshot(deep_snapshot)

        return MemoryUpdateResult(
            session_snapshot=session_snapshot,
            deep_snapshot=deep_snapshot,
            processed_entry_count=len(entries),
        )

    async def _entries_since_anchor(self, *, tape, anchor_name: str) -> list[TapeEntry]:
        query = tape.query_async.kinds("message")
        try:
            return list(await query.after_anchor(anchor_name).all())
        except RepublicError:
            return list(await query.all())

    async def _append_anchor(self, *, tape, name: str, state: dict) -> TapeEntry:
        entry = TapeEntry.anchor(name, state=state)
        await tape.append_async(entry)
        entries = list(await tape.query_async.kinds("anchor").all())
        return entries[-1]

    async def _apply_session_entries(
        self,
        *,
        session_id: str,
        entries: list[TapeEntry],
        initial_snapshot: SessionMemorySnapshot,
    ) -> SessionMemorySnapshot:
        snapshot = initial_snapshot
        for chunk in self._chunk_entries(entries):
            delta = await self.extractor.extract_session_delta(entries=chunk, snapshot=snapshot)
            snapshot = self._merge_session_snapshot(snapshot, delta)
        self.store.save_session_snapshot(snapshot)
        return snapshot

    async def _rebuild_session_from_entries(
        self,
        *,
        session_id: str,
        entries: list[TapeEntry],
        initial_snapshot: SessionMemorySnapshot,
    ) -> SessionMemorySnapshot:
        snapshot = await self._apply_session_entries(
            session_id=session_id,
            entries=entries,
            initial_snapshot=initial_snapshot,
        )
        return snapshot

    def _chunk_entries(self, entries: list[TapeEntry]) -> list[list[TapeEntry]]:
        return [
            entries[index : index + self.chunk_size]
            for index in range(0, len(entries), self.chunk_size)
        ]

    def _merge_session_snapshot(
        self,
        snapshot: SessionMemorySnapshot,
        delta: SessionMemoryDelta,
    ) -> SessionMemorySnapshot:
        return snapshot.model_copy(
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

    def _merge_deep_snapshot(
        self,
        snapshot: DeepMemorySnapshot,
        delta: DeepMemoryDelta,
    ) -> DeepMemorySnapshot:
        return snapshot.model_copy(
            update={
                "revision": snapshot.revision + 1,
                "profile_facts": list(delta.profile_facts),
                "preferences": list(delta.preferences),
                "long_running_projects": list(delta.long_running_projects),
                "stable_workflows": list(delta.stable_workflows),
            }
        )
