import pytest

from friday.plugin import FridayPlugin


class FakeMemoryContext:
    def __init__(self, rendered_prompt: str) -> None:
        self.rendered_prompt = rendered_prompt

    def model_dump(self):
        return {"rendered_prompt": self.rendered_prompt}


class FakeMemoryService:
    def __init__(self) -> None:
        self.load_calls = []
        self.update_calls = []

    async def load_context(self, *, session_id: str, actor_key: str | None):
        self.load_calls.append((session_id, actor_key))
        return FakeMemoryContext("Session Memory\nGoal: Implement memory")

    async def update_memories(self, *, session_id: str, actor_key: str | None):
        self.update_calls.append((session_id, actor_key))


@pytest.mark.anyio
async def test_load_state_includes_message_context_and_memory():
    plugin = FridayPlugin(memory_service=FakeMemoryService())
    message = {
        "channel": "telegram",
        "chat_id": "-1002175041416",
        "content": (
            '{"message":"继续实现 Friday 记忆","sender_id":"6732122782",'
            '"full_name":"Muzych"}'
        ),
    }

    state = await plugin.load_state(message=message, session_id="telegram:-1002175041416")

    assert state["friday_message_context"]["actor_key"] == "telegram:6732122782"
    assert "Session Memory" in state["friday_memory"]["rendered_prompt"]


@pytest.mark.anyio
async def test_save_state_updates_memories_from_state_context():
    memory_service = FakeMemoryService()
    plugin = FridayPlugin(memory_service=memory_service)
    state = {
        "friday_message_context": {
            "actor_key": "telegram:6732122782",
        }
    }

    await plugin.save_state(
        session_id="telegram:-1002175041416",
        state=state,
        message={"content": '{"message":"hello"}'},
        model_output="done",
    )

    assert memory_service.update_calls == [("telegram:-1002175041416", "telegram:6732122782")]


def test_system_prompt_includes_memory_block_and_friday_rules():
    plugin = FridayPlugin(memory_service=FakeMemoryService())
    prompt = plugin.system_prompt(
        "base",
        {"friday_memory": {"rendered_prompt": "Session Memory\nGoal: Implement memory"}},
    )

    assert "Session Memory" in prompt
    assert "You are Friday" in prompt
