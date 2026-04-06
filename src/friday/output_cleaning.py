from __future__ import annotations

import re


_THINK_BLOCK_RE = re.compile(r"(?is)<think>.*?</think>\s*")


def strip_think_blocks(text: str) -> str:
    return _THINK_BLOCK_RE.sub("", text).strip()
