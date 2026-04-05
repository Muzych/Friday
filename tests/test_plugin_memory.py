from dataclasses import dataclass

import pytest

from friday.plugin import FridayPlugin
from friday.memory_settings import resolve_memory_runtime_config


class FakeMemoryContext:
    def __init__(self, rendered_prompt: str) -> None:
        self.rendered_prompt = rendered_prompt

    def model_dump(self):
        return {"rendered_prompt": self.rendered_prompt}


class FakeMemoryService:
    def __init__(self, should_fail: bool = False) -> None:
        self.load_calls = []
        self.update_calls = []
        self.should_fail = should_fail

    async def load_context(self, *, session_id: str, actor_key: str | None):
        self.load_calls.append((session_id, actor_key))
        return FakeMemoryContext("Session Memory\nGoal: Implement memory")

    async def update_memories(self, *, session_id: str, actor_key: str | None):
        if self.should_fail:
            raise RuntimeError("memory write failed")
        self.update_calls.append((session_id, actor_key))


@dataclass
class FakeChannelMessage:
    session_id: str
    channel: str
    content: str
    chat_id: str | None = None
    output_channel: str | None = None


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
async def test_load_state_accepts_attribute_based_channel_message():
    plugin = FridayPlugin(memory_service=FakeMemoryService())
    message = FakeChannelMessage(
        session_id="telegram:-1002175041416",
        channel="telegram",
        chat_id="-1002175041416",
        content=(
            '{"message":"我回来啦","sender_id":"6732122782",'
            '"full_name":"Muzych"}'
        ),
    )

    state = await plugin.load_state(message=message, session_id="telegram:-1002175041416")

    assert state["friday_message_context"]["actor_key"] == "telegram:6732122782"
    assert state["friday_message_context"]["chat_id"] == "-1002175041416"


@pytest.mark.anyio
async def test_load_state_derives_chat_id_from_session_when_message_lacks_it():
    plugin = FridayPlugin(memory_service=FakeMemoryService())
    message = FakeChannelMessage(
        session_id="telegram:-1002175041416",
        channel="telegram",
        content='{"message":"我回来啦","sender_id":"6732122782"}',
    )
    message.output_channel = "null"

    state = await plugin.load_state(message=message, session_id="telegram:-1002175041416")

    assert state["friday_message_context"]["chat_id"] == "-1002175041416"


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


@pytest.mark.anyio
async def test_save_state_does_not_raise_when_memory_update_fails():
    plugin = FridayPlugin(memory_service=FakeMemoryService(should_fail=True))

    await plugin.save_state(
        session_id="telegram:-1002175041416",
        state={"friday_message_context": {"actor_key": "telegram:6732122782"}},
        message={"content": '{"message":"hello"}'},
        model_output="done",
    )


def test_system_prompt_includes_memory_block_and_friday_rules():
    plugin = FridayPlugin(memory_service=FakeMemoryService())
    prompt = plugin.system_prompt(
        "base",
        {"friday_memory": {"rendered_prompt": "Session Memory\nGoal: Implement memory"}},
    )

    assert "Session Memory" in prompt
    assert "You are Friday" in prompt


def test_resolve_memory_runtime_config_reads_explicit_memory_env(monkeypatch):
    monkeypatch.setenv("FRIDAY_MEMORY_MODEL", "openai:gpt-5-mini")
    monkeypatch.setenv("FRIDAY_MEMORY_API_KEY", "memory-key")
    monkeypatch.setenv("FRIDAY_MEMORY_API_BASE", "https://memory.example.com")
    monkeypatch.setenv("FRIDAY_MEMORY_API_FORMAT", "responses")

    config = resolve_memory_runtime_config()

    assert config.model == "openai:gpt-5-mini"
    assert config.api_key == "memory-key"
    assert config.api_base == "https://memory.example.com"
    assert config.api_format == "responses"


def test_resolve_memory_runtime_config_requires_explicit_memory_env(monkeypatch):
    monkeypatch.delenv("FRIDAY_MEMORY_MODEL", raising=False)
    monkeypatch.delenv("FRIDAY_MEMORY_API_KEY", raising=False)
    monkeypatch.delenv("FRIDAY_MEMORY_API_BASE", raising=False)
    monkeypatch.delenv("FRIDAY_MEMORY_API_FORMAT", raising=False)

    with pytest.raises(RuntimeError, match="FRIDAY_MEMORY_MODEL"):
        resolve_memory_runtime_config()
