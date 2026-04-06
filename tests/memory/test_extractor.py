import pytest
from republic import TapeEntry

from friday.memory.extractor import (
    MemoryExtractor,
    render_entries_for_extraction,
)
from friday.memory.models import DeepMemoryDelta, DeepMemorySnapshot, SessionMemorySnapshot


def test_render_entries_for_extraction_strips_think_blocks():
    entries = [
        TapeEntry.message({"role": "assistant", "content": "<think>private</think>\nVisible reply"}),
        TapeEntry.system("<think>hidden</think>\nKeep this instruction"),
        TapeEntry.anchor("session_memory/snapshot", state={"revision": 1}),
    ]

    rendered = render_entries_for_extraction(entries)

    assert rendered == "assistant: Visible reply\nsystem: Keep this instruction"


class FakeLLM:
    def __init__(self, calls):
        self.calls = calls
        self.kwargs = None

    async def tool_calls_async(self, **kwargs):
        self.kwargs = kwargs
        return self.calls


@pytest.mark.anyio
async def test_extract_deep_delta_uses_named_tool_call():
    llm = FakeLLM(
        [
            {
                "function": {
                    "name": "emit_deep_memory_delta",
                    "arguments": (
                        '{"profile_facts":["User is building Friday."],'
                        '"preferences":[],"long_running_projects":["Friday"],'
                        '"stable_workflows":["Uses Bub"]}'
                    ),
                }
            }
        ]
    )
    extractor = MemoryExtractor(llm)

    delta = await extractor.extract_deep_delta(
        entries=[],
        session_snapshot=SessionMemorySnapshot(session_id="telegram:1", summary="Working on Friday memory"),
        snapshot=DeepMemorySnapshot(actor_key="telegram:user"),
    )

    assert delta.long_running_projects == ["Friday"]
    assert llm.kwargs["tool_choice"] == {
        "type": "function",
        "function": {"name": "emit_deep_memory_delta"},
    }
    assert llm.kwargs["parallel_tool_calls"] is False
    assert llm.kwargs["temperature"] == 0.1
