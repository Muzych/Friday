"""Friday's Bub plugin."""

from __future__ import annotations

from typing import Any

from bub import hookimpl


class FridayPlugin:
    """Project-level Bub customization for Friday."""

    @hookimpl
    def system_prompt(self, prompt: str | list[dict], state: dict[str, Any]) -> str:
        return (
            "You are Friday, a warm, precise agent for this workspace. "
            "Read the project context before acting, keep changes small, "
            "and prefer faithful general algorithms over brittle patches."
        )


friday_plugin = FridayPlugin()
