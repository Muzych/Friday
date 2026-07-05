# Friday

Friday is a Bub-powered agent workspace.

## Quick Start

```bash
uv sync
uv run bub hooks
uv run bub run ",help"
```

## Run

Use the Bub CLI directly:

```bash
uv run bub chat
uv run bub run "Summarize this workspace."
uv run bub gateway
```

Or use the project command, which delegates to the same Bub CLI with Friday's plugin installed:

```bash
uv run friday hooks
uv run friday run ",help"
```

## Telegram

Copy `.env.example` to `.env`, set `BUB_TELEGRAM_TOKEN`, and restrict access with `BUB_TELEGRAM_ALLOW_USERS` or `BUB_TELEGRAM_ALLOW_CHATS`.

```bash
uv run bub gateway --enable-channel telegram
```
