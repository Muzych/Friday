import pytest

from nowledge_mem_bub.client import NmemError

from friday import nowledge_tools


class MissingThreadClient:
    async def fetch_thread(self, thread_id: str, limit: int = 20, offset: int = 0):
        raise NmemError(
            '{\n  "error": "api_error",\n  "status_code": 404,\n  "detail": "Thread not found"\n}'
        )


class WorkingThreadClient:
    async def fetch_thread(self, thread_id: str, limit: int = 20, offset: int = 0):
        return {
            "title": "Friday Memory",
            "total_messages": 2,
            "messages": [
                {"role": "user", "content": "hello"},
                {"role": "assistant", "content": "hi"},
            ],
            "has_more": False,
        }


@pytest.mark.anyio
async def test_mem_thread_returns_not_found_text_for_missing_thread(monkeypatch):
    monkeypatch.setattr(nowledge_tools, "NmemClient", lambda: MissingThreadClient())

    result = await nowledge_tools.mem_thread_fetch.run(
        "missing-thread",
        context={"tape": "unused"},
    )

    assert result == "Thread not found: missing-thread"


@pytest.mark.anyio
async def test_mem_thread_renders_thread_messages(monkeypatch):
    monkeypatch.setattr(nowledge_tools, "NmemClient", lambda: WorkingThreadClient())

    result = await nowledge_tools.mem_thread_fetch.run(
        "thread-1",
        context={"tape": "unused"},
    )

    assert "Thread: Friday Memory (2 messages)" in result
    assert "[user] hello" in result
    assert "[assistant] hi" in result
