from __future__ import annotations

import os
from dataclasses import dataclass


@dataclass(frozen=True)
class MemoryRuntimeConfig:
    model: str
    api_key: str | dict[str, str] | None
    api_base: str | dict[str, str] | None
    api_format: str


def _require_env(name: str) -> str:
    value = os.environ.get(name)
    if value is None or not value.strip():
        raise RuntimeError(f"Missing required memory setting: {name}")
    return value


def resolve_memory_runtime_config() -> MemoryRuntimeConfig:
    model = _require_env("FRIDAY_MEMORY_MODEL")
    api_key = _require_env("FRIDAY_MEMORY_API_KEY")
    api_base = _require_env("FRIDAY_MEMORY_API_BASE")
    api_format = _require_env("FRIDAY_MEMORY_API_FORMAT")
    return MemoryRuntimeConfig(
        model=model,
        api_key=api_key,
        api_base=api_base,
        api_format=api_format,
    )
