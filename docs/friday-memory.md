# Friday Memory

Friday now uses a three-layer memory architecture:

- `tape`
  The only source of truth for Friday-owned memory.
- `session_memory`
  Single-session task state keyed by `session_id`.
- `deep_memory`
  Stable cross-session facts keyed by `channel + sender_id`.
- `Nowledge Mem`
  External cross-tool semantic memory provided by the `nowledge_mem` plugin.

## Ownership

Friday owns:

- `session_memory`
- `deep_memory`

Friday does not own:

- Nowledge Mem storage
- Nowledge Mem retrieval logic

## Local Snapshot Storage

Friday stores local derived snapshots under Bub home:

- `~/.bub/friday_memory/session_memory/`
- `~/.bub/friday_memory/deep_memory/`

These files are derived snapshots, not a second source of truth.

## Tape Anchors

Friday appends dedicated anchors into tape:

- `session_memory/snapshot`
- `deep_memory/snapshot`

They mark the last successful memory update for incremental processing.

## Commands

Show local memory:

```bash
uv run bub friday-memory-show --session-id telegram:-1002175041416
uv run bub friday-memory-show --actor-key telegram:6732122782
```

Rebuild local memory from tape:

```bash
uv run bub friday-memory-rebuild --session-id telegram:-1002175041416
uv run bub friday-memory-rebuild --session-id telegram:-1002175041416 --actor-key telegram:6732122782
```

## Runtime

When Friday handles a turn:

1. It loads `session_memory`
2. It loads `deep_memory`
3. It lets `nowledge_mem` inject external semantic memory
4. It prepends compact local memory blocks into the system prompt
5. After the turn finishes, it updates local snapshots from tape

## Important Boundary

`session_memory` stores only current-session task state.

`deep_memory` stores only stable cross-session facts.

Nowledge Mem remains the external semantic memory layer and is not duplicated into Friday-owned storage.
