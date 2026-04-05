import pytest

from friday.memory.extractor import (
    MemoryExtractor,
    decode_json_object,
    parse_deep_memory_delta,
    parse_session_memory_delta,
)
from friday.memory.models import DeepMemoryDelta, DeepMemorySnapshot, SessionMemorySnapshot


def test_parse_session_memory_delta_from_model_json():
    payload = {
        "goal": "Implement Friday memory",
        "active_tasks": ["Add plugin integration"],
        "constraints": ["Tape is the only source of truth"],
        "open_questions": [],
        "recent_decisions": ["Use session_memory and deep_memory"],
        "follow_ups": ["Write CLI commands"],
        "summary": "User is implementing the new memory architecture.",
    }

    delta = parse_session_memory_delta(payload)

    assert delta.goal == "Implement Friday memory"
    assert delta.active_tasks == ["Add plugin integration"]


def test_parse_deep_memory_delta_from_model_json():
    payload = {
        "profile_facts": ["User is building Friday."],
        "preferences": ["Prefers deterministic designs."],
        "long_running_projects": ["Friday memory system"],
        "stable_workflows": ["Uses Bub as orchestration layer."],
    }

    delta = parse_deep_memory_delta(payload)

    assert delta.profile_facts == ["User is building Friday."]
    assert delta.long_running_projects == ["Friday memory system"]


def test_decode_json_object_accepts_markdown_fenced_json():
    raw = """```json
    {
      "goal": "Implement Friday memory",
      "active_tasks": ["Add plugin integration"]
    }
    ```"""

    payload = decode_json_object(raw)

    assert payload["goal"] == "Implement Friday memory"


class FakeLLM:
    def __init__(self, response_text: str):
        self.response_text = response_text
        self.kwargs = None

    async def chat_async(self, **kwargs):
        self.kwargs = kwargs
        return self.response_text


@pytest.mark.anyio
async def test_extract_deep_delta_uses_response_format_schema():
    llm = FakeLLM(
        '{"profile_facts":["User is building Friday."],'
        '"preferences":[],"long_running_projects":["Friday"],'
        '"stable_workflows":["Uses Bub"]}'
    )
    extractor = MemoryExtractor(llm)

    delta = await extractor.extract_deep_delta(
        entries=[],
        session_snapshot=SessionMemorySnapshot(session_id="telegram:1", summary="Working on Friday memory"),
        snapshot=DeepMemorySnapshot(actor_key="telegram:user"),
    )

    assert delta.long_running_projects == ["Friday"]
    assert llm.kwargs["response_format"] is DeepMemoryDelta
