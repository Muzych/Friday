from __future__ import annotations

from typing import Any

from bub import hookimpl
from bub.envelope import content_of, field_of
from bub.builtin.settings import load_settings
from loguru import logger

from friday.cli import register_memory_commands
from friday.memory.service import MemoryService
from friday.memory_settings import resolve_memory_runtime_config
from friday.message_context import parse_message_context
from friday import nowledge_tools as _nowledge_tools

FRIDAY_BASE_PROMPT = """\
You are Friday, a helpful Telegram group assistant.
Rules:
- Reply clearly and briefly.
- In group chats, prefer responding only to explicit user intent.
- If the message is ambiguous, ask one short clarifying question.
- Do not invent facts.
"""


class FridayPlugin:
    def __init__(self, framework: Any | None = None, memory_service: MemoryService | None = None) -> None:
        self.framework = framework
        self.memory_service = memory_service or self._build_memory_service()

    def _build_memory_service(self) -> MemoryService | None:
        if self.framework is None:
            return None
        tape_store = self.framework.get_tape_store()
        if tape_store is None:
            return None
        settings = load_settings()
        memory_config = resolve_memory_runtime_config()
        return MemoryService.from_runtime(
            root=settings.home / "friday_memory",
            workspace=self.framework.workspace,
            model=memory_config.model,
            api_key=memory_config.api_key,
            api_base=memory_config.api_base,
            api_format=memory_config.api_format,
            tape_store=tape_store,
            context=self.framework.build_tape_context(),
        )

    @hookimpl
    async def load_state(self, message, session_id):
        if self.memory_service is None:
            return {}
        context = self._parse_context(message, session_id)
        memory = await self.memory_service.load_context(
            session_id=context.session_key,
            actor_key=context.actor_key,
        )
        return {
            "friday_message_context": context.model_dump(),
            "friday_memory": memory.model_dump(),
        }

    @hookimpl
    async def save_state(self, session_id, state, message, model_output):
        if self.memory_service is None:
            return
        context_data = state.get("friday_message_context")
        actor_key = context_data.get("actor_key") if isinstance(context_data, dict) else None
        try:
            await self.memory_service.update_memories(
                session_id=session_id,
                actor_key=actor_key,
            )
        except Exception as exc:
            logger.warning("friday memory update failed: {}", exc)

    @hookimpl
    def system_prompt(self, prompt, state):
        memory_prompt = ""
        friday_memory = state.get("friday_memory")
        if isinstance(friday_memory, dict):
            memory_prompt = str(friday_memory.get("rendered_prompt", "")).strip()
        parts = [memory_prompt, FRIDAY_BASE_PROMPT]
        return "\n\n".join(part for part in parts if part)

    @hookimpl
    def register_cli_commands(self, app):
        if self.memory_service is not None:
            register_memory_commands(app, self.memory_service)

    def _parse_context(self, message: Any, session_id: str):
        channel = str(field_of(message, "channel", "default"))
        raw_chat_id = field_of(message, "chat_id")
        chat_id = str(raw_chat_id) if raw_chat_id is not None else session_id.split(":", 1)[-1]
        raw_content = content_of(message)
        return parse_message_context(
            channel=channel,
            session_id=session_id,
            chat_id=chat_id,
            raw_content=raw_content,
        )
