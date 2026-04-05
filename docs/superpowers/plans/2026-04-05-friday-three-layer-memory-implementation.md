# Friday Three-Layer Memory Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build Friday-owned `session_memory` and `deep_memory` on top of tape while keeping Nowledge Mem as the existing external semantic memory layer.

**Architecture:** Keep Bub/Republic tape as the append-only source of truth. Add two derived snapshot stores: `session_memory` keyed by `session_id` for single-session task state, and `deep_memory` keyed by `channel + sender_id` for stable cross-session facts. Update both stores incrementally from tape entries after the latest memory anchors, then inject compact prompt blocks before model execution while leaving `nowledge_mem` plugin behavior intact.

**Tech Stack:** Python 3.12, Bub hooks, Republic tape APIs, Pydantic models, pytest, uv, nowledge-mem-bub

---

## Scope

This plan supersedes the earlier two-layer memory draft in [2026-04-01-friday-memory-mechanism.md](/Users/woodson/Project/Friday/docs/superpowers/plans/2026-04-01-friday-memory-mechanism.md).

This implementation covers only Friday-owned memory layers:

- `session_memory`
- `deep_memory`

This implementation does not replace or reimplement:

- `nowledge_mem` plugin hooks
- Nowledge Mem storage
- cross-tool semantic retrieval

## File Structure

- Modify: `pyproject.toml`
  Add direct dependencies for memory models and tests.
- Modify: `src/friday/plugin.py`
  Replace the prompt-only plugin with hook integration for state loading, memory updates, and prompt injection.
- Create: `src/friday/cli.py`
  Register operator commands for showing and rebuilding local memory snapshots.
- Create: `src/friday/message_context.py`
  Parse channel/session/actor identity from inbound Bub messages.
- Create: `src/friday/memory/__init__.py`
  Export memory-layer public interfaces.
- Create: `src/friday/memory/models.py`
  Define typed models for snapshots, deltas, anchors, and renderable memory context.
- Create: `src/friday/memory/store.py`
  Persist `session_memory` and `deep_memory` snapshots under Bub home and apply deterministic merge logic.
- Create: `src/friday/memory/extractor.py`
  Build typed extraction prompts and parse structured deltas for both memory layers.
- Create: `src/friday/memory/prompting.py`
  Render compact prompt blocks for `session_memory` and `deep_memory`.
- Create: `src/friday/memory/service.py`
  Coordinate tape reads, snapshot loads, delta extraction, anchor writes, rebuilds, and prompt preparation.
- Create: `tests/test_message_context.py`
  Verify message identity parsing and actor/session key derivation.
- Create: `tests/memory/test_store.py`
  Verify snapshot persistence and deterministic merge behavior.
- Create: `tests/memory/test_extractor.py`
  Verify structured extraction contracts for session and deep deltas.
- Create: `tests/memory/test_prompting.py`
  Verify compact, deterministic prompt rendering.
- Create: `tests/memory/test_service.py`
  Verify incremental tape processing, anchor handling, and rebuild behavior.
- Create: `tests/test_plugin_memory.py`
  Verify Bub hook integration and prompt injection order with `nowledge_mem`.
- Create: `docs/friday-memory.md`
  Document memory model, operator commands, and rebuild workflow.

## Design Notes

- `tape` remains the only source of truth.
- `session_memory` stores only single-session task state:
  - goal
  - active tasks
  - constraints
  - open questions
  - recent decisions
  - unresolved follow-ups
- `deep_memory` stores only stable cross-session facts:
  - identity facts
  - preferences
  - long-running projects
  - recurring workflows
- Promotion from `session_memory` into `deep_memory` must be explicit and typed.
- Use separate anchors:
  - `session_memory/snapshot`
  - `deep_memory/snapshot`
- Keep `nowledge_mem` as an external semantic layer and do not duplicate its prompt block.

## Compatibility Checkpoint

Before implementing the memory layers, the engineer must verify these framework surfaces still exist in the current installed versions:

- Bub hooks:
  - `load_state`
  - `save_state`
  - `system_prompt`
  - `register_cli_commands`
- Republic tape APIs needed for incremental processing:
  - session/tape lookup
  - append anchor entries
  - query entries after a known anchor
- Existing `nowledge_mem` plugin behavior:
  - `build_prompt`
  - `save_state`
  - `system_prompt`

If any of these drift, fix the plan locally before implementing more code.

### Task 1: Add Memory Dependencies And Test Scaffold

**Files:**
- Modify: `pyproject.toml`
- Modify: `uv.lock`

- [ ] **Step 1: Add direct dependencies for memory modeling and test execution**

```toml
[project]
dependencies = [
    "black>=26.3.1",
    "bub>=0.3.3",
    "nmem-cli>=0.6.9",
    "nowledge-mem-bub>=0.2.2",
    "pydantic>=2.11.0",
    "republic>=0.7.0",
]

[dependency-groups]
dev = [
    "pytest>=8.3.0",
]
```

- [ ] **Step 2: Refresh the lockfile and environment**

Run: `uv sync --group dev`
Expected: sync succeeds and installs `pytest`.

- [ ] **Step 3: Verify the toolchain before adding feature tests**

Run: `uv run pytest --version`
Expected: a `pytest 8.x` version line prints.

- [ ] **Step 4: Commit the dependency scaffold**

```bash
git add pyproject.toml uv.lock
git commit -m "chore: add friday memory dependencies"
```

### Task 2: Parse Bub Message Context Into Stable Session And Actor Keys

**Files:**
- Create: `src/friday/message_context.py`
- Test: `tests/test_message_context.py`

- [ ] **Step 1: Write failing tests for context parsing**

```python
from friday.message_context import parse_message_context


def test_parse_telegram_context_builds_session_and_actor_keys():
    raw = (
        '{"message":"继续实现 Friday 记忆","message_id":42,"type":"text",'
        '"username":"Muzy_ch","full_name":"Muzych","sender_id":"6732122782",'
        '"sender_is_bot":false,"date":1774754554.0}'
    )

    ctx = parse_message_context(
        channel="telegram",
        session_id="telegram:-1002175041416",
        chat_id="-1002175041416",
        raw_content=raw,
    )

    assert ctx.session_key == "telegram:-1002175041416"
    assert ctx.actor_key == "telegram:6732122782"
    assert ctx.display_name == "Muzych"
```

- [ ] **Step 2: Run the parser test to confirm it fails**

Run: `uv run pytest tests/test_message_context.py -v`
Expected: FAIL because parser symbols do not exist yet.

- [ ] **Step 3: Implement a focused `MessageContext` model and parser**

```python
from pydantic import BaseModel
import json


class MessageContext(BaseModel):
    channel: str
    session_key: str
    actor_key: str | None
    chat_id: str
    sender_id: str | None
    display_name: str | None
    message_text: str


def parse_message_context(*, channel: str, session_id: str, chat_id: str, raw_content: str) -> MessageContext:
    payload = json.loads(raw_content)
    sender_id = payload.get("sender_id")
    return MessageContext(
        channel=channel,
        session_key=session_id,
        actor_key=f"{channel}:{sender_id}" if sender_id else None,
        chat_id=chat_id,
        sender_id=sender_id,
        display_name=payload.get("full_name") or payload.get("username"),
        message_text=payload.get("message", ""),
    )
```

- [ ] **Step 4: Run the parser tests to confirm they pass**

Run: `uv run pytest tests/test_message_context.py -v`
Expected: PASS

- [ ] **Step 5: Commit the context layer**

```bash
git add src/friday/message_context.py tests/test_message_context.py
git commit -m "feat: derive friday session and actor keys"
```

### Task 3: Add Typed Snapshot Models And Deterministic Store Logic

**Files:**
- Create: `src/friday/memory/__init__.py`
- Create: `src/friday/memory/models.py`
- Create: `src/friday/memory/store.py`
- Test: `tests/memory/test_store.py`

- [ ] **Step 1: Write failing tests for snapshot merge and persistence**

```python
from friday.memory.models import SessionMemoryDelta, SessionMemorySnapshot
from friday.memory.store import MemoryStore


def test_session_memory_merge_updates_goal_and_tasks(tmp_path):
    store = MemoryStore(tmp_path)
    snapshot = store.load_session_snapshot("telegram:-1002175041416")

    delta = SessionMemoryDelta(
        goal="Implement Friday memory",
        active_tasks=["Add memory store"],
        constraints=["Tape is the only source of truth"],
        open_questions=[],
        recent_decisions=[],
        follow_ups=["Write tests"],
        summary="User is implementing Friday memory.",
    )

    updated = store.apply_session_delta("telegram:-1002175041416", delta)
    assert updated.goal == "Implement Friday memory"
    assert updated.active_tasks == ["Add memory store"]
```

- [ ] **Step 2: Run the store tests to confirm they fail**

Run: `uv run pytest tests/memory/test_store.py -v`
Expected: FAIL because memory store code does not exist yet.

- [ ] **Step 3: Implement typed snapshots and deterministic merge rules**

```python
class SessionMemorySnapshot(BaseModel):
    session_id: str
    revision: int = 0
    summary: str = ""
    goal: str = ""
    active_tasks: list[str] = []
    constraints: list[str] = []
    open_questions: list[str] = []
    recent_decisions: list[str] = []
    follow_ups: list[str] = []
    last_anchor_id: str | None = None


class DeepMemorySnapshot(BaseModel):
    actor_key: str
    revision: int = 0
    profile_facts: list[str] = []
    preferences: list[str] = []
    long_running_projects: list[str] = []
    stable_workflows: list[str] = []
    last_anchor_id: str | None = None
```

```python
def merge_session_snapshot(snapshot: SessionMemorySnapshot, delta: SessionMemoryDelta) -> SessionMemorySnapshot:
    return snapshot.model_copy(
        update={
            "revision": snapshot.revision + 1,
            "summary": delta.summary or snapshot.summary,
            "goal": delta.goal or snapshot.goal,
            "active_tasks": delta.active_tasks,
            "constraints": delta.constraints,
            "open_questions": delta.open_questions,
            "recent_decisions": delta.recent_decisions,
            "follow_ups": delta.follow_ups,
        }
    )
```

- [ ] **Step 4: Run the store tests to confirm they pass**

Run: `uv run pytest tests/memory/test_store.py -v`
Expected: PASS

- [ ] **Step 5: Commit the snapshot store**

```bash
git add src/friday/memory/__init__.py src/friday/memory/models.py src/friday/memory/store.py tests/memory/test_store.py
git commit -m "feat: add friday memory snapshot store"
```

### Task 4: Add Structured Extractors For Session And Deep Memory Deltas

**Files:**
- Create: `src/friday/memory/extractor.py`
- Test: `tests/memory/test_extractor.py`

- [ ] **Step 1: Write failing tests for typed extractor contracts**

```python
from friday.memory.extractor import parse_deep_memory_delta, parse_session_memory_delta


def test_parse_session_memory_delta_from_model_json():
    payload = {
        "goal": "Implement Friday memory",
        "active_tasks": ["Add plugin integration"],
        "constraints": ["Tape is the only source of truth"],
        "open_questions": [],
        "recent_decisions": ["Use session_memory and deep_memory"],
        "follow_ups": ["Write CLI commands"],
        "summary": "User is implementing the new memory architecture."
    }

    delta = parse_session_memory_delta(payload)
    assert delta.goal == "Implement Friday memory"
    assert delta.active_tasks == ["Add plugin integration"]
```

- [ ] **Step 2: Run extractor tests to confirm they fail**

Run: `uv run pytest tests/memory/test_extractor.py -v`
Expected: FAIL because extractor code does not exist yet.

- [ ] **Step 3: Implement separate typed extraction paths**

```python
SESSION_MEMORY_SCHEMA = {
    "goal": "string",
    "active_tasks": ["string"],
    "constraints": ["string"],
    "open_questions": ["string"],
    "recent_decisions": ["string"],
    "follow_ups": ["string"],
    "summary": "string",
}

DEEP_MEMORY_SCHEMA = {
    "profile_facts": ["string"],
    "preferences": ["string"],
    "long_running_projects": ["string"],
    "stable_workflows": ["string"],
}
```

- [ ] **Step 4: Run extractor tests to confirm they pass**

Run: `uv run pytest tests/memory/test_extractor.py -v`
Expected: PASS

- [ ] **Step 5: Commit the extractor layer**

```bash
git add src/friday/memory/extractor.py tests/memory/test_extractor.py
git commit -m "feat: add structured friday memory extractors"
```

### Task 5: Render Compact Prompt Blocks For Session And Deep Memory

**Files:**
- Create: `src/friday/memory/prompting.py`
- Test: `tests/memory/test_prompting.py`

- [ ] **Step 1: Write failing prompt-rendering tests**

```python
from friday.memory.models import DeepMemorySnapshot, SessionMemorySnapshot
from friday.memory.prompting import render_memory_blocks


def test_render_memory_blocks_orders_session_before_deep():
    session = SessionMemorySnapshot(
        session_id="telegram:-100",
        goal="Implement memory",
        active_tasks=["Write tests"],
        constraints=["No heuristics"],
    )
    deep = DeepMemorySnapshot(
        actor_key="telegram:6732122782",
        preferences=["Prefers deterministic designs"],
    )

    rendered = render_memory_blocks(session, deep)
    assert rendered.index("Session Memory") < rendered.index("Deep Memory")
    assert "Write tests" in rendered
    assert "Prefers deterministic designs" in rendered
```

- [ ] **Step 2: Run prompt tests to confirm they fail**

Run: `uv run pytest tests/memory/test_prompting.py -v`
Expected: FAIL because prompting code does not exist yet.

- [ ] **Step 3: Implement deterministic prompt rendering**

```python
def render_memory_blocks(session: SessionMemorySnapshot | None, deep: DeepMemorySnapshot | None) -> str:
    sections: list[str] = []
    if session:
        sections.append(render_session_block(session))
    if deep:
        sections.append(render_deep_block(deep))
    return "\n\n".join(section for section in sections if section.strip())
```

- [ ] **Step 4: Run prompt tests to confirm they pass**

Run: `uv run pytest tests/memory/test_prompting.py -v`
Expected: PASS

- [ ] **Step 5: Commit prompt rendering**

```bash
git add src/friday/memory/prompting.py tests/memory/test_prompting.py
git commit -m "feat: render friday memory prompt blocks"
```

### Task 6: Implement Tape-Backed Memory Service With Incremental Anchors

**Files:**
- Create: `src/friday/memory/service.py`
- Test: `tests/memory/test_service.py`

- [ ] **Step 1: Write failing service tests for incremental updates**

```python
async def test_update_session_memory_reads_only_entries_after_last_anchor(...):
    service = MemoryService(...)
    result = await service.update_session_memory(
        session_id="telegram:-1002175041416",
        actor_key="telegram:6732122782",
    )
    assert result.processed_entry_count == 2
    assert result.session_snapshot.revision == 1
```

- [ ] **Step 2: Run the service tests to confirm they fail**

Run: `uv run pytest tests/memory/test_service.py -v`
Expected: FAIL because service code does not exist yet.

- [ ] **Step 3: Implement incremental service methods**

```python
class MemoryService:
    async def load_context(self, *, session_id: str, actor_key: str | None) -> RenderableMemoryContext: ...
    async def update_session_memory(self, *, session_id: str, actor_key: str | None, message, model_output) -> SessionUpdateResult: ...
    async def update_deep_memory(self, *, actor_key: str, session_snapshot: SessionMemorySnapshot, entries: list) -> DeepUpdateResult: ...
    async def rebuild_session_memory(self, *, session_id: str) -> SessionMemorySnapshot: ...
    async def rebuild_deep_memory(self, *, actor_key: str) -> DeepMemorySnapshot: ...
```

- [ ] **Step 4: Append dedicated memory anchors after successful updates**

```python
await tape.append_async(
    TapeEntry.anchor(
        "session_memory/snapshot",
        {"session_id": session_id, "revision": snapshot.revision, "schema_version": 1},
    )
)
```

- [ ] **Step 5: Run the service tests to confirm they pass**

Run: `uv run pytest tests/memory/test_service.py -v`
Expected: PASS

- [ ] **Step 6: Commit the memory service**

```bash
git add src/friday/memory/service.py tests/memory/test_service.py
git commit -m "feat: update friday memory snapshots from tape"
```

### Task 7: Integrate Friday Plugin Hooks Without Replacing Nowledge Mem

**Files:**
- Modify: `src/friday/plugin.py`
- Test: `tests/test_plugin_memory.py`

- [ ] **Step 1: Write failing hook integration tests**

```python
async def test_system_prompt_includes_local_memory_without_overwriting_nowledge_guidance():
    plugin = FridayPlugin(...)
    prompt = await plugin.system_prompt("base", {"friday_memory": {"rendered": "Session Memory"}})
    assert "Session Memory" in prompt
    assert "Nowledge Mem" not in prompt
```

- [ ] **Step 2: Run plugin tests to confirm they fail**

Run: `uv run pytest tests/test_plugin_memory.py -v`
Expected: FAIL because the plugin only returns a static prompt today.

- [ ] **Step 3: Implement `load_state`, `save_state`, and `system_prompt` integration**

```python
class FridayPlugin:
    @hookimpl
    async def load_state(self, session_id, state, message):
        ctx = parse_message_context(...)
        memory = await self.memory_service.load_context(
            session_id=ctx.session_key,
            actor_key=ctx.actor_key,
        )
        return {
            "friday_message_context": ctx.model_dump(),
            "friday_memory": memory.model_dump(),
        }

    @hookimpl
    async def save_state(self, session_id, state, message, model_output):
        ctx = state["friday_message_context"]
        await self.memory_service.update_session_memory(...)
        if ctx["actor_key"]:
            await self.memory_service.update_deep_memory(...)

    @hookimpl
    def system_prompt(self, prompt, state):
        rendered = state.get("friday_memory", {}).get("rendered_prompt", "")
        return "\n\n".join(part for part in [prompt or "", rendered, FRIDAY_BASE_PROMPT] if part.strip())
```

- [ ] **Step 4: Run plugin tests to confirm they pass**

Run: `uv run pytest tests/test_plugin_memory.py -v`
Expected: PASS

- [ ] **Step 5: Commit plugin integration**

```bash
git add src/friday/plugin.py tests/test_plugin_memory.py
git commit -m "feat: integrate friday session and deep memory hooks"
```

### Task 8: Add Operator CLI Commands And User-Facing Docs

**Files:**
- Create: `src/friday/cli.py`
- Create: `docs/friday-memory.md`

- [ ] **Step 1: Add failing smoke checks for CLI registration**

Run: `uv run bub hooks`
Expected: `register_cli_commands: builtin` only, and no Friday memory commands yet.

- [ ] **Step 2: Implement CLI registration and rebuild/show commands**

```python
def register_memory_commands(app, memory_service):
    @app.command("friday-memory-show")
    def friday_memory_show(session_id: str | None = None, actor_key: str | None = None): ...

    @app.command("friday-memory-rebuild")
    def friday_memory_rebuild(session_id: str): ...

    @app.command("friday-memory-rebuild-deep")
    def friday_memory_rebuild_deep(actor_key: str): ...
```

- [ ] **Step 3: Document the memory architecture and rebuild workflow**

Document:
- the difference between `session_memory`, `deep_memory`, and `Nowledge Mem`
- where local snapshots are stored
- what memory anchors mean
- how to inspect or rebuild a snapshot

- [ ] **Step 4: Run CLI verification**

Run: `uv run bub --help`
Expected: Friday memory commands appear in the CLI output.

- [ ] **Step 5: Commit CLI and docs**

```bash
git add src/friday/cli.py docs/friday-memory.md
git commit -m "docs: add friday memory operator workflow"
```

## Final Verification

- [ ] Run: `uv run pytest`
- [ ] Run: `uv run bub hooks`
- [ ] Run: `set -a; source .env; set +a; uv run nmem status`
- [ ] Run: `uv run bub friday-memory-show --session-id telegram:-1002175041416`
- [ ] Run: `uv run bub friday-memory-rebuild --session-id telegram:-1002175041416`
- [ ] Run: `set -a; source .env; set +a; uv run bub gateway --enable-channel telegram`

Expected:

- test suite passes
- `nowledge_mem` still appears in Bub hooks
- local memory commands are registered
- session and deep snapshots rebuild from tape
- Telegram gateway still starts with the memory-enabled plugin

## Acceptance Criteria

- Friday stores `session_memory` for single-session task state only.
- Friday stores `deep_memory` for stable cross-session facts only.
- Both memory layers are derived from tape and rebuildable from tape.
- `session_memory` and `deep_memory` use separate anchors.
- Prompt injection is compact, deterministic, and layered ahead of Friday guidance.
- `Nowledge Mem` remains integrated as an external semantic memory layer.
- Operator commands exist for show and rebuild workflows.
