import json
from typing import Any

from pydantic import BaseModel
from republic import LLM, TapeEntry

from friday.memory.models import (
    DeepMemoryDelta,
    DeepMemorySnapshot,
    SessionMemoryDelta,
    SessionMemorySnapshot,
)


def parse_session_memory_delta(payload: dict[str, Any]) -> SessionMemoryDelta:
    return SessionMemoryDelta.model_validate(payload)


def parse_deep_memory_delta(payload: dict[str, Any]) -> DeepMemoryDelta:
    return DeepMemoryDelta.model_validate(payload)


def decode_json_object(raw: str) -> dict[str, Any]:
    decoder = json.JSONDecoder()
    for start, char in enumerate(raw):
        if char != "{":
            continue
        try:
            payload, end = decoder.raw_decode(raw[start:])
        except json.JSONDecodeError:
            continue
        if isinstance(payload, dict):
            return payload
    raise json.JSONDecodeError("No JSON object found", raw, 0)


def render_entries_for_extraction(entries: list[TapeEntry]) -> str:
    rendered: list[str] = []
    for entry in entries:
        if entry.kind == "message":
            role = str(entry.payload.get("role", "unknown"))
            content = str(entry.payload.get("content", "")).strip()
            if content:
                rendered.append(f"{role}: {content}")
            continue
        if entry.kind == "system":
            content = str(entry.payload.get("content", "")).strip()
            if content:
                rendered.append(f"system: {content}")
    return "\n".join(rendered)


class MemoryExtractor:
    def __init__(self, llm: LLM) -> None:
        self._llm = llm

    async def extract_session_delta(
        self,
        *,
        entries: list[TapeEntry],
        snapshot: SessionMemorySnapshot,
    ) -> SessionMemoryDelta:
        return await self._extract_structured_json(
            model_cls=SessionMemoryDelta,
            system_prompt=_session_extractor_prompt(snapshot),
            transcript=render_entries_for_extraction(entries),
        )

    async def extract_deep_delta(
        self,
        *,
        entries: list[TapeEntry],
        session_snapshot: SessionMemorySnapshot,
        snapshot: DeepMemorySnapshot,
    ) -> DeepMemoryDelta:
        return await self._extract_structured_json(
            model_cls=DeepMemoryDelta,
            system_prompt=_deep_extractor_prompt(session_snapshot, snapshot),
            transcript=session_snapshot.model_dump_json(),
        )

    async def _extract_structured_json(
        self,
        *,
        model_cls: type[BaseModel],
        system_prompt: str,
        transcript: str,
    ) -> BaseModel:
        raw = await self._llm.chat_async(
            prompt=transcript,
            system_prompt=system_prompt,
            response_format=model_cls,
            max_tokens=800,
        )
        return model_cls.model_validate_json(raw)


def _session_extractor_prompt(snapshot: SessionMemorySnapshot) -> str:
    return (
        "Extract only single-session task state from the transcript. "
        "Do not infer durable user facts. Return only one JSON object and nothing else. "
        "Every field value must match the requested type exactly. Return strict JSON with keys: "
        "goal, active_tasks, constraints, open_questions, recent_decisions, follow_ups, summary. "
        f"Current session snapshot: {snapshot.model_dump_json()}"
    )


def _deep_extractor_prompt(
    session_snapshot: SessionMemorySnapshot,
    snapshot: DeepMemorySnapshot,
) -> str:
    return (
        "Extract only stable cross-session user facts from the provided session-memory snapshot. "
        "Do not include temporary task state, active tasks, or unresolved follow-ups. "
        "Return only one JSON object and nothing else. "
        "Each array item must be a plain string, never an object. "
        "Return strict JSON with keys: "
        "profile_facts, preferences, long_running_projects, stable_workflows. "
        f"Current session snapshot to promote from: {session_snapshot.model_dump_json()} "
        f"Current deep snapshot: {snapshot.model_dump_json()}"
    )
