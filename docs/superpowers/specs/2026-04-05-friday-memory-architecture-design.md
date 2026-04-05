# Friday Memory Architecture Design

## Goal

Design and implement a three-layer memory system for Friday:

1. `session_memory`
   Single-session task state derived from tape. This layer tracks what the user is trying to do in the current conversation and what remains unresolved.
2. `deep_memory`
   Cross-session stable user facts derived from tape. This layer stores durable information that should remain true across future Friday conversations.
3. `Nowledge Mem`
   Cross-tool semantic memory provided by the existing `nowledge_mem` Bub plugin integration. This layer is already integrated and remains an external memory surface rather than a Friday-owned data store.

`tape` remains the only source of truth for Friday-owned memory. `session_memory` and `deep_memory` are both derived snapshots that can always be rebuilt from tape.

## Boundaries

### Tape

- Append-only source of truth
- Stores the raw conversation and tool activity
- Stores memory snapshot anchors and revision metadata

### Session Memory

- Keyed by `session_id`
- Scope: one Friday conversation session
- Purpose: track active task execution state
- Includes:
  - current goal
  - active tasks
  - constraints
  - open questions
  - recent decisions
  - unresolved follow-ups
  - compact session summary
- Excludes:
  - cross-session stable preferences
  - durable user profile facts
  - global semantic retrieval across external tools

### Deep Memory

- Keyed by a stable actor identity, initially `channel + sender_id`
- Scope: cross-session Friday memory for the same user
- Purpose: store durable user facts that continue to matter in future conversations
- Includes:
  - stable preferences
  - identity facts
  - long-running projects
  - recurring workflows
  - durable collaboration patterns
- Excludes:
  - transient task state from a single session
  - speculative or weakly inferred facts

### Nowledge Mem

- External semantic memory layer
- Already integrated through `nowledge-mem-bub`
- Not a substitute for Friday-owned `session_memory` or `deep_memory`
- Used for:
  - cross-tool recall
  - semantic search over broader personal context
  - optional working memory injection through the plugin

## Core Principles

- `tape` is the only truth source for Friday-owned memory.
- `session_memory` and `deep_memory` must always be rebuildable from tape.
- No regex heuristics, keyword bandages, or ad hoc post-processing.
- Memory mutation happens only through explicit structured extraction.
- Promotion from `session_memory` to `deep_memory` is explicit, typed, and deterministic.

## Recommended Architecture

Friday will maintain two local derived snapshot stores:

- `session_memory` store
- `deep_memory` store

Each store records:

- current snapshot payload
- snapshot revision
- last processed tape anchor metadata
- timestamps

Friday updates these stores incrementally after each completed turn by reading only tape entries that occurred after the relevant last snapshot anchor.

## Data Model

### Session Memory Snapshot

Suggested shape:

```json
{
  "session_id": "telegram:-1002175041416",
  "revision": 3,
  "summary": "User is connecting Bub, Telegram, and memory systems for Friday.",
  "goal": "Design and implement Friday memory architecture.",
  "active_tasks": [
    "Define memory layers",
    "Implement tape-derived memory snapshots"
  ],
  "constraints": [
    "Tape is the only source of truth",
    "No heuristic extraction"
  ],
  "open_questions": [],
  "recent_decisions": [
    "Session memory stores only single-session task state",
    "Deep memory stores stable cross-session facts"
  ],
  "follow_ups": [
    "Implement session and deep memory stores"
  ],
  "last_anchor": {
    "kind": "session_memory/snapshot",
    "tape_id": "..."
  }
}
```

### Deep Memory Snapshot

Suggested shape:

```json
{
  "actor_key": "telegram:6732122782",
  "revision": 2,
  "profile_facts": [
    "User is building Friday."
  ],
  "preferences": [
    "Prefers tape-backed deterministic memory design."
  ],
  "long_running_projects": [
    "Friday memory system"
  ],
  "stable_workflows": [
    "Uses Bub as the orchestration layer."
  ],
  "last_anchor": {
    "kind": "deep_memory/snapshot",
    "tape_id": "..."
  }
}
```

### Structured Delta Types

Two separate extraction outputs are required:

1. `SessionMemoryDelta`
   Allowed to update only session-scoped fields.
2. `DeepMemoryDelta`
   Allowed to update only stable cross-session fields.

This separation avoids accidental leakage of temporary task state into durable memory.

## Update Flow

### After Each Completed Turn

1. Load current message context
   Derive `session_id`, `channel`, `chat_id`, and `sender_id`.
2. Load current `session_memory` snapshot
3. Query tape entries since the last `session_memory/snapshot` anchor
4. Run structured extraction for `SessionMemoryDelta`
5. Merge delta into `session_memory`
6. Write updated `session_memory` snapshot
7. Append a `session_memory/snapshot` anchor to tape
8. Evaluate whether any newly confirmed facts should become `DeepMemoryDelta`
9. Merge approved durable facts into `deep_memory`
10. Write updated `deep_memory` snapshot
11. Append a `deep_memory/snapshot` anchor to tape

### Read Path Before Model Invocation

1. Load `session_memory` by `session_id`
2. Load `deep_memory` by actor identity
3. Let `nowledge_mem` inject its own working-memory / recall layer
4. Render a compact prompt block in this order:
   - session task state
   - deep stable facts
   - external Nowledge context

## Identity Strategy

Initial actor identity rule:

- `actor_key = f"{channel}:{sender_id}"`

This is the correct first version because it is deterministic and derived from the inbound Telegram payload without extra inference.

Future identity linking across channels can be added later, but it must be explicit and audited rather than inferred heuristically.

## Snapshot Anchors

Friday will use two anchor kinds:

- `session_memory/snapshot`
- `deep_memory/snapshot`

Each anchor payload should contain enough metadata to support incremental rebuilds:

- snapshot type
- revision
- actor key or session id
- timestamp
- schema version

## Prompt Injection

### Session Memory Prompt Block

Should remain short and operational:

- current goal
- active tasks
- important constraints
- unresolved questions
- recent decisions

### Deep Memory Prompt Block

Should remain short and durable:

- stable user preferences
- long-running projects
- durable context that helps future responses

### Nowledge Mem Prompt Block

Handled by the installed plugin. Friday should not duplicate this layer.

## Why Session Memory Is Still Necessary

Even with tape as source of truth and Nowledge Mem already integrated, `session_memory` is still required because:

- replaying raw tape every turn is expensive and unstable
- task state is different from long-term semantic knowledge
- a single-session execution summary should not pollute durable memory
- Nowledge Mem is cross-tool semantic memory, not Friday's canonical task-state layer

## Why Deep Memory Is Still Necessary

`deep_memory` is needed because:

- Friday needs a controlled, product-owned cross-session memory layer
- stable user facts should not be mixed with session task state
- promotion rules must be explicit and deterministic
- Friday must be able to rebuild its own durable memory from tape without depending on external semantic stores

## Storage Strategy

Suggested local storage under Bub home:

- `session_memory/<session_id>.json`
- `deep_memory/<actor_key>.json`

This store is a cache of derived snapshots, not a second source of truth.

## Hooks

Friday's plugin should eventually own:

- `load_state`
  Load message context plus both local memory layers
- `save_state`
  Update `session_memory` and `deep_memory` from new tape entries
- `system_prompt`
  Inject compact local memory blocks
- `register_cli_commands`
  Provide operator commands for inspect and rebuild

The existing `nowledge_mem` plugin continues to supply:

- external working memory injection
- semantic retrieval guidance
- session digest capture into Nowledge Mem

## CLI Requirements

Friday should add explicit operator commands:

- `friday-memory-show --session-id ...`
- `friday-memory-show --actor-key ...`
- `friday-memory-rebuild --session-id ...`
- `friday-memory-rebuild-deep --actor-key ...`

These commands should read and rebuild derived snapshots from tape without mutating tape history beyond new snapshot anchors.

## Testing Requirements

Tests must cover:

- session delta extraction
- deep delta extraction
- deterministic merge behavior
- anchor creation
- incremental updates from last anchor
- rebuild from tape
- prompt rendering
- actor identity derivation

## Recommended Implementation Direction

Proceed with a tape-backed, incremental, dual-snapshot architecture:

- `session_memory` for single-session task state
- `deep_memory` for stable cross-session facts
- `Nowledge Mem` retained as external semantic memory via plugin

This gives Friday a clean ownership boundary:

- operational memory stays local and deterministic
- durable Friday-specific memory stays rebuildable from tape
- cross-tool semantic memory remains delegated to Nowledge Mem

## Next Step

Create an implementation plan that updates the existing memory plan to this three-layer architecture and then execute it in phases:

1. message identity parsing
2. memory models and stores
3. session extraction and merge
4. deep extraction and promotion
5. plugin hook integration
6. CLI and tests
