from __future__ import annotations

import asyncio
import json

import typer

from friday.memory.service import MemoryService


def register_memory_commands(app: typer.Typer, memory_service: MemoryService) -> None:
    @app.command("friday-memory-show")
    def friday_memory_show(
        session_id: str | None = typer.Option(None, "--session-id"),
        actor_key: str | None = typer.Option(None, "--actor-key"),
    ) -> None:
        payload: dict[str, object] = {}
        if session_id:
            payload["session_memory"] = memory_service.get_session_snapshot(session_id).model_dump()
        if actor_key:
            payload["deep_memory"] = memory_service.get_deep_snapshot(actor_key).model_dump()
        typer.echo(json.dumps(payload, ensure_ascii=False, indent=2))

    @app.command("friday-memory-rebuild")
    def friday_memory_rebuild(
        session_id: str = typer.Option(..., "--session-id"),
        actor_key: str | None = typer.Option(None, "--actor-key"),
    ) -> None:
        result = asyncio.run(
            memory_service.rebuild_session_memory(session_id=session_id, actor_key=actor_key)
        )
        typer.echo(
            json.dumps(
                {
                    "processed_entry_count": result.processed_entry_count,
                    "session_memory": result.session_snapshot.model_dump(),
                    "deep_memory": result.deep_snapshot.model_dump() if result.deep_snapshot else None,
                },
                ensure_ascii=False,
                indent=2,
            )
        )
