from __future__ import annotations

from typing import Any

from bub import tool
from nowledge_mem_bub.client import NmemClient, NmemError


@tool(context=True, name="mem.thread")
async def mem_thread_fetch(
    thread_id: str,
    offset: int = 0,
    limit: int = 20,
    *,
    context: Any,
) -> str:
    """Fetch messages from a specific thread, returning a stable result when the thread no longer exists."""
    del context
    client = NmemClient()
    try:
        result = await client.fetch_thread(thread_id, limit=limit, offset=offset)
    except NmemError as exc:
        error_text = str(exc).lower()
        if "not found" not in error_text and "404" not in error_text:
            raise
        return f"Thread not found: {thread_id}"

    title = result.get("title", "")
    total = result.get("total_messages", result.get("message_count", "?"))
    messages = result.get("messages", [])
    has_more = result.get("has_more", len(messages) >= limit)

    lines = [f"Thread: {title} ({total} messages)"]
    for msg in messages:
        role = msg.get("role", "")
        text = msg.get("content", "")[:600]
        lines.append(f"[{role}] {text}")

    if has_more:
        next_offset = offset + len(messages)
        lines.append(f"\n(more messages available — use offset={next_offset})")

    return "\n".join(lines)
