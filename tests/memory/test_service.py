import pytest
from republic import LLM, TapeEntry
from republic.tape import InMemoryTapeStore

from friday.memory.models import DeepMemoryDelta, SessionMemoryDelta
from friday.memory.service import MemoryService


class FakeExtractor:
    def __init__(self) -> None:
        self.session_entry_counts: list[int] = []
        self.deep_entry_counts: list[int] = []

    async def extract_session_delta(self, *, entries, snapshot):
        self.session_entry_counts.append(len(entries))
        return SessionMemoryDelta(
            goal=f"goal-{len(entries)}",
            active_tasks=[f"task-{len(entries)}"],
            constraints=["Tape is the only source of truth"],
            open_questions=[],
            recent_decisions=[],
            follow_ups=[],
            summary=f"summary-{len(entries)}",
        )

    async def extract_deep_delta(self, *, entries, session_snapshot, snapshot):
        self.deep_entry_counts.append(len(entries))
        return DeepMemoryDelta(
            profile_facts=[f"profile-{len(entries)}"],
            preferences=["deterministic"],
            long_running_projects=["Friday"],
            stable_workflows=["Bub"],
        )


@pytest.mark.anyio
async def test_update_memories_reads_only_entries_after_last_anchor(tmp_path):
    tape_store = InMemoryTapeStore()
    llm = LLM(model="openai:MiniMax-M2.7", tape_store=tape_store)
    extractor = FakeExtractor()
    service = MemoryService(
        root=tmp_path,
        workspace=tmp_path,
        llm=llm,
        extractor=extractor,
    )
    tape = service.tape_for_session("telegram:-1002175041416")

    await tape.append_async(TapeEntry.message({"role": "user", "content": "first"}))
    await tape.append_async(TapeEntry.message({"role": "assistant", "content": "second"}))

    first = await service.update_memories(
        session_id="telegram:-1002175041416",
        actor_key="telegram:6732122782",
    )

    assert first.session_snapshot.revision == 1
    assert first.deep_snapshot is not None
    assert first.deep_snapshot.revision == 1
    assert extractor.session_entry_counts == [2]
    assert extractor.deep_entry_counts == [2]

    await tape.append_async(TapeEntry.message({"role": "user", "content": "third"}))
    await tape.append_async(TapeEntry.message({"role": "assistant", "content": "fourth"}))

    second = await service.update_memories(
        session_id="telegram:-1002175041416",
        actor_key="telegram:6732122782",
    )

    assert second.session_snapshot.revision == 2
    assert second.deep_snapshot is not None
    assert second.deep_snapshot.revision == 2
    assert extractor.session_entry_counts == [2, 2]
    assert extractor.deep_entry_counts == [2, 2]


@pytest.mark.anyio
async def test_load_context_renders_session_and_deep_memory(tmp_path):
    tape_store = InMemoryTapeStore()
    llm = LLM(model="openai:MiniMax-M2.7", tape_store=tape_store)
    service = MemoryService(
        root=tmp_path,
        workspace=tmp_path,
        llm=llm,
        extractor=FakeExtractor(),
    )
    service.store.apply_session_delta(
        "telegram:-1002175041416",
        SessionMemoryDelta(goal="Implement memory", active_tasks=["Write tests"]),
    )
    service.store.apply_deep_delta(
        "telegram:6732122782",
        DeepMemoryDelta(preferences=["deterministic"]),
    )

    context = await service.load_context(
        session_id="telegram:-1002175041416",
        actor_key="telegram:6732122782",
    )

    assert context.session_snapshot.goal == "Implement memory"
    assert context.deep_snapshot is not None
    assert "Session Memory" in context.rendered_prompt
    assert "Deep Memory" in context.rendered_prompt


@pytest.mark.anyio
async def test_rebuild_session_memory_processes_entries_in_chunks(tmp_path):
    tape_store = InMemoryTapeStore()
    llm = LLM(model="openai:MiniMax-M2.7", tape_store=tape_store)
    extractor = FakeExtractor()
    service = MemoryService(
        root=tmp_path,
        workspace=tmp_path,
        llm=llm,
        extractor=extractor,
        chunk_size=2,
    )
    tape = service.tape_for_session("telegram:-1002175041416")

    for idx in range(5):
        await tape.append_async(TapeEntry.message({"role": "user", "content": f"msg-{idx}"}))

    result = await service.rebuild_session_memory(
        session_id="telegram:-1002175041416",
        actor_key="telegram:6732122782",
    )

    assert extractor.session_entry_counts == [2, 2, 1]
    assert result.session_snapshot.revision == 3
