# Friday Memory Mechanism Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a tape-backed memory mechanism for Friday that can persist stable facts across turns and inject relevant memory into future prompts.

**Architecture:** Keep Bub/Republic tape as the append-only source of truth, then add a deterministic memory layer on top of it. Each completed turn reads new tape entries since the last `memory/snapshot` anchor, extracts a structured memory delta with a dedicated LLM call, merges that delta into persisted memory snapshots, and injects compact session/user memory back through `system_prompt`.

**Tech Stack:** Python 3.12, Bub hooks, Republic tape store/query APIs, Pydantic models, pytest, uv

---

## File Structure

- Modify: `pyproject.toml`
  Add direct dependencies needed by the new memory code and test runner setup.
- Create: `src/friday/cli.py`
  Register operator-facing memory inspection and rebuild commands through Bub’s `register_cli_commands` hook.
- Create: `src/friday/message_context.py`
  Parse inbound Telegram payloads and derive deterministic memory identity keys such as `channel`, `chat_id`, and `sender_id`.
- Create: `src/friday/memory/models.py`
  Define the typed schema for memory items, memory deltas, snapshots, and anchor metadata.
- Create: `src/friday/memory/store.py`
  Persist session and actor memory snapshots under Bub home, and implement deterministic merge rules.
- Create: `src/friday/memory/extractor.py`
  Convert tape entries into a structured extraction prompt and parse the model’s JSON delta.
- Create: `src/friday/memory/service.py`
  Orchestrate tape reads, delta extraction, snapshot merge, anchor writes, and prompt rendering.
- Modify: `src/friday/plugin.py`
  Replace the current prompt-only plugin with full `load_state`, `save_state`, and `system_prompt` memory integration.
- Create: `tests/test_message_context.py`
  Unit tests for inbound payload parsing and identity derivation.
- Create: `tests/memory/test_store.py`
  Unit tests for merge behavior and on-disk snapshot persistence.
- Create: `tests/memory/test_extractor.py`
  Unit tests for transcript selection and JSON delta parsing.
- Create: `tests/memory/test_service.py`
  Integration-style tests for reading from tape, updating memory, and anchoring snapshots.
- Create: `tests/test_plugin_memory.py`
  Hook-level tests to verify memory is loaded into state and injected into the prompt.
- Create: `docs/friday-memory.md`
  Operator-facing explanation of how memory is stored, rebuilt, and inspected.

## Design Notes

- Tape remains the only raw conversation ledger. Memory snapshots are derived artifacts.
- Maintain two scopes:
  - `actor` memory: stable facts keyed by `channel + sender_id`, so the same human can be remembered across chats.
  - `session` memory: recent conversation context keyed by session/tape, so chat-local details do not leak globally.
- Only explicit structured deltas may mutate memory. No regex heuristics or post-processing bandages.
- Every successful memory update writes a `memory/snapshot` tape anchor containing revision metadata so future updates can query only new entries.
- Memory injection should be compact and deterministic:
  - stable actor facts first
  - then current session summary
  - then open threads / current focus

## Compatibility Checkpoint

These framework surfaces were verified before writing this plan:

- Bub hook contract already includes `load_state`, `save_state`, `system_prompt`, and `register_cli_commands`, so the memory integration can be implemented as a normal plugin hook chain.
- Republic’s tape session API already includes:
  - `tape.query_async`
  - `tape.handoff_async(...)`
  - `tape.append_async(...)`
  - `TapeEntry.message/system/anchor/event`
- The implementation should still start by adding a narrow compatibility test that exercises these exact APIs from Friday’s plugin layer, so any future Bub/Republic version drift fails fast.

### Task 1: Add Test And Dependency Scaffold

**Files:**
- Modify: `pyproject.toml`
- Modify: `uv.lock`

- [ ] **Step 1: Add direct project dependencies for memory work and tests**

```toml
[project]
dependencies = [
    "black>=26.3.1",
    "bub>=0.3.2",
    "pydantic>=2.11.0",
    "republic>=0.7.0",
]

[dependency-groups]
dev = [
    "pytest>=8.3.0",
]
```

- [ ] **Step 2: Refresh the lockfile and local environment**

Run: `uv sync --group dev`
Expected: environment refresh completes and `pytest` is installed.

- [ ] **Step 3: Verify the test runner works before adding feature tests**

Run: `uv run pytest --version`
Expected: a `pytest 8.x` version line prints.

- [ ] **Step 4: Commit the dependency bootstrap**

```bash
git add pyproject.toml uv.lock
git commit -m "chore: add memory planning dependencies"
```

### Task 2: Parse Inbound Context Into Stable Memory Identities

**Files:**
- Create: `src/friday/message_context.py`
- Test: `tests/test_message_context.py`

- [ ] **Step 1: Write the failing tests for Telegram payload parsing**

```python
from friday.message_context import MessageContext, parse_message_context


def test_parse_telegram_user_identity_from_message_payload():
    raw = (
        '{"message":"你好","message_id":674,"type":"text",'
        '"username":"Muzy_ch","full_name":"Muzych","sender_id":"6732122782",'
        '"sender_is_bot":false,"date":1774754554.0}'
    )

    ctx = parse_message_context(
        channel="telegram",
        session_id="telegram:-1002175041416",
        chat_id="-1002175041416",
        raw_content=raw,
    )

    assert ctx.actor_key == "telegram:6732122782"
    assert ctx.session_key == "telegram:-1002175041416"
    assert ctx.display_name == "Muzych"
```

- [ ] **Step 2: Run the parser test to verify it fails**

Run: `uv run pytest tests/test_message_context.py -v`
Expected: FAIL with `ModuleNotFoundError` or missing parser symbols.

- [ ] **Step 3: Implement a focused parser and identity model**

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
    actor_key = f"{channel}:{sender_id}" if sender_id else None
    return MessageContext(
        channel=channel,
        session_key=session_id,
        actor_key=actor_key,
        chat_id=chat_id,
        sender_id=sender_id,
        display_name=payload.get("full_name") or payload.get("username"),
        message_text=payload.get("message", ""),
    )
```

- [ ] **Step 4: Run the parser test to verify it passes**

Run: `uv run pytest tests/test_message_context.py -v`
Expected: PASS

- [ ] **Step 5: Commit the parsing layer**

```bash
git add src/friday/message_context.py tests/test_message_context.py
git commit -m "feat: parse message context for memory identities"
```

### Task 3: Add Deterministic Memory Models And Snapshot Store

**Files:**
- Create: `src/friday/memory/models.py`
- Create: `src/friday/memory/store.py`
- Test: `tests/memory/test_store.py`

- [ ] **Step 1: Write failing tests for merge semantics and snapshot persistence**

```python
from friday.memory.models import MemoryDelta, MemoryFact
from friday.memory.store import MemoryStore


def test_merge_replaces_existing_fact_for_same_slot(tmp_path):
    store = MemoryStore(tmp_path)
    store.save_actor_snapshot(
        "telegram:6732122782",
        [MemoryFact(scope="actor", slot="profile.current_project", value="Friday UI", evidence_entry_ids=[10])],
    )

    delta = MemoryDelta(
        upserts=[MemoryFact(scope="actor", slot="profile.current_project", value="Friday memory system", evidence_entry_ids=[20])],
        deletes=[],
        session_summary=None,
    )

    snapshot = store.apply_actor_delta("telegram:6732122782", delta)
    assert snapshot.facts["profile.current_project"].value == "Friday memory system"
    assert snapshot.facts["profile.current_project"].evidence_entry_ids == [20]
```

- [ ] **Step 2: Run the store tests to verify they fail**

Run: `uv run pytest tests/memory/test_store.py -v`
Expected: FAIL because memory models/store do not exist yet.

- [ ] **Step 3: Implement typed snapshots and deterministic merge rules**

```python
class MemoryFact(BaseModel):
    scope: Literal["actor", "session"]
    slot: str
    value: str
    evidence_entry_ids: list[int]


class MemoryDelta(BaseModel):
    upserts: list[MemoryFact]
    deletes: list[str]
    session_summary: str | None = None


class MemorySnapshot(BaseModel):
    revision: int
    facts: dict[str, MemoryFact]
    session_summary: str | None = None
```

```python
def apply_delta(snapshot: MemorySnapshot, delta: MemoryDelta) -> MemorySnapshot:
    facts = dict(snapshot.facts)
    for slot in delta.deletes:
        facts.pop(slot, None)
    for fact in delta.upserts:
        facts[fact.slot] = fact
    return snapshot.model_copy(
        update={
            "revision": snapshot.revision + 1,
            "facts": facts,
            "session_summary": delta.session_summary or snapshot.session_summary,
        }
    )
```

- [ ] **Step 4: Persist snapshots under Bub home with separate actor/session namespaces**

```python
memory_root/
  actor/<identity>.json
  session/<identity>.json
```

Use `state["_runtime_agent"].settings.home / "memory"` as the root when wiring the store into production code.

- [ ] **Step 5: Run store tests to verify they pass**

Run: `uv run pytest tests/memory/test_store.py -v`
Expected: PASS

- [ ] **Step 6: Commit the storage layer**

```bash
git add src/friday/memory/models.py src/friday/memory/store.py tests/memory/test_store.py
git commit -m "feat: add persistent memory snapshots"
```

### Task 4: Build Tape-To-Memory Extraction

**Files:**
- Create: `src/friday/memory/extractor.py`
- Test: `tests/memory/test_extractor.py`

- [ ] **Step 1: Write failing tests for tape entry selection and delta parsing**

```python
from republic.tape.entries import TapeEntry
from friday.memory.extractor import build_memory_transcript, parse_memory_delta


def test_build_memory_transcript_ignores_system_entries():
    entries = [
        TapeEntry.system("system prompt"),
        TapeEntry.message({"role": "user", "content": "我最近在做 Friday 的 working memory"}),
        TapeEntry.message({"role": "assistant", "content": "听起来很有意思"}),
    ]

    transcript = build_memory_transcript(entries)

    assert "working memory" in transcript
    assert "system prompt" not in transcript
```

- [ ] **Step 2: Run the extractor tests to verify they fail**

Run: `uv run pytest tests/memory/test_extractor.py -v`
Expected: FAIL because extractor functions do not exist yet.

- [ ] **Step 3: Implement a dedicated extraction prompt and strict JSON parser**

```python
MEMORY_EXTRACTION_PROMPT = """
Extract durable actor facts and current session summary from the transcript.
Return JSON with this exact schema:
{
  "upserts": [{"scope": "actor|session", "slot": "...", "value": "...", "evidence_entry_ids": [1,2]}],
  "deletes": ["slot.name"],
  "session_summary": "..."
}
Only include facts explicitly supported by the transcript.
"""
```

- [ ] **Step 4: Implement transcript building from tape entries**

```python
def build_memory_transcript(entries: Iterable[TapeEntry]) -> str:
    lines = []
    for entry in entries:
        if entry.kind != "message":
            continue
        role = entry.payload.get("role")
        content = entry.payload.get("content", "").strip()
        if not content:
            continue
        lines.append(f"[{entry.id}] {role}: {content}")
    return "\n".join(lines)
```

- [ ] **Step 5: Parse extraction responses with schema validation**

Run: `uv run pytest tests/memory/test_extractor.py -v`
Expected: PASS

- [ ] **Step 6: Commit the extraction layer**

```bash
git add src/friday/memory/extractor.py tests/memory/test_extractor.py
git commit -m "feat: extract structured memory deltas from tape"
```

### Task 5: Orchestrate Memory Updates From Tape And Anchor Them

**Files:**
- Create: `src/friday/memory/service.py`
- Test: `tests/memory/test_service.py`

- [ ] **Step 1: Write failing tests for “entries since last memory anchor” behavior**

```python
async def test_update_from_tape_reads_only_entries_after_last_memory_anchor(fake_runtime_agent, tmp_path):
    service = MemoryService(...)
    tape = fake_runtime_agent.tapes.session_tape("telegram:-100", tmp_path)

    await tape.append_async(TapeEntry.anchor("memory/snapshot", {"revision": 1}))
    await tape.append_async(TapeEntry.message({"role": "user", "content": "记住，我是 Muzych"}))

    result = await service.update_from_tape(
        runtime_agent=fake_runtime_agent,
        session_id="telegram:-100",
        actor_key="telegram:6732122782",
        workspace=tmp_path,
    )

    assert result.updated is True
```

- [ ] **Step 2: Run the service tests to verify they fail**

Run: `uv run pytest tests/memory/test_service.py -v`
Expected: FAIL because the service layer does not exist yet.

- [ ] **Step 3: Implement the orchestration service**

```python
class MemoryService:
    async def update_from_tape(self, *, runtime_agent, session_id: str, actor_key: str | None, workspace: Path):
        tape = runtime_agent.tapes.session_tape(session_id, workspace)
        entries = list(await tape.query_async.after_anchor("memory/snapshot").all())
        if not entries:
            entries = list(await tape.query_async.after_anchor("session/start").all())
        transcript = build_memory_transcript(entries)
        delta = await self.extractor.extract(transcript)
        ...
        await tape.handoff_async("memory/snapshot", state={"revision": revision, "actor_key": actor_key})
```

- [ ] **Step 4: Use a dedicated LLM client for extraction, not the agent loop**

Construct a standalone `republic.LLM` from Bub settings so memory extraction does not recurse through `run_model`.

- [ ] **Step 5: Run service tests to verify they pass**

Run: `uv run pytest tests/memory/test_service.py -v`
Expected: PASS

- [ ] **Step 6: Commit the orchestration layer**

```bash
git add src/friday/memory/service.py tests/memory/test_service.py
git commit -m "feat: update memory snapshots from tape"
```

### Task 6: Integrate Memory Into Friday Hooks

**Files:**
- Modify: `src/friday/plugin.py`
- Test: `tests/test_plugin_memory.py`

- [ ] **Step 1: Write failing hook tests for memory loading and prompt injection**

```python
async def test_system_prompt_includes_actor_and_session_memory(tmp_path):
    plugin = FridayPlugin(...)
    state = {
        "session_id": "telegram:-1002175041416",
        "_runtime_workspace": str(tmp_path),
        "friday_memory": {
            "actor_facts": {"profile.name": "Muzych"},
            "session_summary": "User is building Friday working memory.",
        },
    }

    prompt = plugin.system_prompt("hello", state)

    assert "Muzych" in prompt
    assert "working memory" in prompt
```

- [ ] **Step 2: Run the hook tests to verify they fail**

Run: `uv run pytest tests/test_plugin_memory.py -v`
Expected: FAIL because the plugin does not load or inject memory yet.

- [ ] **Step 3: Replace the current plugin with full hook implementations**

```python
class FridayPlugin:
    def __init__(self) -> None:
        self.memory_service = MemoryService(...)

    @hookimpl
    async def load_state(self, message, session_id):
        ctx = parse_message_context(...)
        memory_state = await self.memory_service.load_context(...)
        return {"friday_message_context": ctx.model_dump(), "friday_memory": memory_state}

    @hookimpl
    async def save_state(self, session_id, state, message, model_output):
        await self.memory_service.update_from_message(...)

    @hookimpl
    def system_prompt(self, prompt, state):
        memory_block = render_memory_block(state.get("friday_memory", {}))
        return BASE_PROMPT + "\n\n" + memory_block
```

- [ ] **Step 4: Keep prompt rendering compact and deterministic**

Render only:
- actor facts sorted by slot
- session summary
- open topics if explicitly stored

- [ ] **Step 5: Run the hook tests to verify they pass**

Run: `uv run pytest tests/test_plugin_memory.py -v`
Expected: PASS

- [ ] **Step 6: Run the full test suite**

Run: `uv run pytest`
Expected: all tests PASS

- [ ] **Step 7: Commit the hook integration**

```bash
git add src/friday/plugin.py tests/test_plugin_memory.py
git commit -m "feat: inject tape-backed memory into friday prompts"
```

### Task 7: Add Operator Tooling And Documentation

**Files:**
- Create: `src/friday/cli.py`
- Modify: `src/friday/plugin.py`
- Create: `docs/friday-memory.md`

- [ ] **Step 1: Add CLI commands for inspection and rebuild**

Register commands through Bub’s existing `register_cli_commands(self, app)` hook, with the command implementations living in `src/friday/cli.py`.

```python
from friday.cli import register_memory_commands


@hookimpl
def register_cli_commands(self, app):
    register_memory_commands(app, self.memory_service)
```

Implement command functions such as:

```python
def register_memory_commands(app, memory_service):
    @app.command("friday-memory-show")
    def friday_memory_show(session_id: str, actor_key: str | None = None): ...

    @app.command("friday-memory-rebuild")
    def friday_memory_rebuild(session_id: str): ...
```

- [ ] **Step 2: Document memory storage and rebuild workflow**

Include:
- where snapshots live
- what `memory/snapshot` anchor means
- how to rebuild from tape after schema changes
- how to inspect a user/session memory snapshot

- [ ] **Step 3: Verify commands render help successfully**

Run: `uv run bub --help`
Expected: Friday memory commands appear in the CLI output.

- [ ] **Step 4: Smoke-test rebuild against an existing tape**

Run: `uv run bub friday-memory-rebuild --session-id telegram:-1002175041416`
Expected: a session snapshot is rebuilt and a summary of updated revisions is printed.

- [ ] **Step 5: Commit tooling and docs**

```bash
git add src/friday/cli.py src/friday/plugin.py docs/friday-memory.md
git commit -m "docs: add friday memory operator workflow"
```

## Final Verification

- [ ] Run: `uv run pytest`
- [ ] Run: `uv run bub hooks`
- [ ] Run: `uv run bub friday-memory-show --session-id telegram:-1002175041416`
- [ ] Restart Friday gateway after merge:

```bash
uv run bub gateway --enable-channel telegram
```

## Acceptance Criteria

- Friday remembers stable user facts across turns without re-reading the whole tape.
- Friday can remember a user across separate chats when `sender_id` is stable.
- Memory updates are derived only from tape entries after the last `memory/snapshot` anchor.
- Memory snapshots can be rebuilt from tape if the schema changes.
- Prompt injection stays compact and deterministic.
- The entire feature is covered by automated tests and operator docs.
