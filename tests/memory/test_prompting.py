from friday.memory.models import DeepMemorySnapshot, SessionMemorySnapshot
from friday.memory.prompting import render_memory_blocks


def test_render_memory_blocks_orders_session_before_deep():
    session = SessionMemorySnapshot(
        session_id="telegram:-100",
        goal="Implement memory",
        active_tasks=["Write tests"],
        constraints=["No heuristics"],
    )
    deep = DeepMemorySnapshot(
        actor_key="telegram:6732122782",
        preferences=["Prefers deterministic designs"],
    )

    rendered = render_memory_blocks(session, deep)

    assert rendered.index("Session Memory") < rendered.index("Deep Memory")
    assert "Write tests" in rendered
    assert "Prefers deterministic designs" in rendered
