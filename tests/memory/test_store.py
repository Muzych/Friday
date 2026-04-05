from friday.memory.models import DeepMemoryDelta, SessionMemoryDelta
from friday.memory.store import MemoryStore


def test_session_memory_merge_updates_goal_and_tasks(tmp_path):
    store = MemoryStore(tmp_path)

    delta = SessionMemoryDelta(
        goal="Implement Friday memory",
        active_tasks=["Add memory store"],
        constraints=["Tape is the only source of truth"],
        open_questions=[],
        recent_decisions=[],
        follow_ups=["Write tests"],
        summary="User is implementing Friday memory.",
    )

    updated = store.apply_session_delta("telegram:-1002175041416", delta)

    assert updated.goal == "Implement Friday memory"
    assert updated.active_tasks == ["Add memory store"]
    assert updated.constraints == ["Tape is the only source of truth"]
    assert updated.follow_ups == ["Write tests"]
    assert updated.revision == 1


def test_deep_memory_merge_persists_stable_facts(tmp_path):
    store = MemoryStore(tmp_path)

    delta = DeepMemoryDelta(
        profile_facts=["User is building Friday."],
        preferences=["Prefers deterministic designs."],
        long_running_projects=["Friday memory system"],
        stable_workflows=["Uses Bub as orchestration layer."],
    )

    updated = store.apply_deep_delta("telegram:6732122782", delta)
    reloaded = store.load_deep_snapshot("telegram:6732122782")

    assert updated.profile_facts == ["User is building Friday."]
    assert updated.preferences == ["Prefers deterministic designs."]
    assert updated.revision == 1
    assert reloaded == updated
