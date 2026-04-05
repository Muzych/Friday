from dataclasses import dataclass

import pytest

from friday.output_cleaning import strip_think_blocks
from friday.plugin import FridayPlugin


def test_strip_think_blocks_removes_internal_reasoning():
    raw = "<think>internal reasoning</think>\n\nHello from Friday."

    assert strip_think_blocks(raw) == "Hello from Friday."


@dataclass
class FakeOutbound:
    content: str


@pytest.mark.anyio
async def test_dispatch_outbound_strips_think_blocks_from_message_content():
    plugin = FridayPlugin(memory_service=None)
    outbound = FakeOutbound(content="<think>internal</think>\nVisible answer")

    await plugin.dispatch_outbound(outbound)

    assert outbound.content == "Visible answer"
