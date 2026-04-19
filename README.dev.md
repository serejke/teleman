# Developer Guide

Technical reference for setting up, configuring, and extending teleman.

## Prerequisites

- Python 3.11+
- [uv](https://docs.astral.sh/uv/)

```bash
uv sync
```

## Accounts

Each account is a pair of files in `accounts/`:

```
accounts/
  15551234567.json      # API credentials
  15551234567.session   # Telethon session file (auto-created)
```

The JSON file:

```json
{
  "app_id": 12345,
  "app_hash": "your_api_hash",
  "phone": "+15551234567"
}
```

Get `app_id` and `app_hash` from [my.telegram.org](https://my.telegram.org). On first run, Telethon prompts for the login code to create the session file.

```bash
# Run with a specific account
uv run python -m teleman --account 15551234567

# Pick from available accounts interactively
uv run python -m teleman
```

## Proxy

Create `accounts/proxies.json` for per-account proxies. Every account needs an entry — use `null` for direct connections.

```json
{
  "15551234567": {
    "type": "http",
    "addr": "proxy.example.com",
    "port": 8080,
    "username": "user",
    "password": "secret"
  },
  "15559876543": null
}
```

Supported types: `http`, `socks5`, `socks4`. `username` and `password` are optional.

## Configuration

Optionally create a `.env` to override the accounts directory:

```
ACCOUNTS_DIR=accounts
```

## CLI Commands

### Interactive REPL

| Command                                                    | Description                                     |
| ---------------------------------------------------------- | ----------------------------------------------- |
| `/me`                                                      | Show current account info                       |
| `/chats`                                                   | List recent dialogs                             |
| `/chat <user>`                                             | Open a chat with a user or group                |
| `/add <user>`                                              | Add contact                                     |
| `/contacts`                                                | List contacts                                   |
| `/nuke <user>`                                             | Delete all messages and remove chat             |
| `/privacy`                                                 | Show privacy settings                           |
| `/privacy_set <key> <level>`                               | Set a privacy key                               |
| `/lockdown`                                                | Set all privacy to `nobody`                     |
| `/settings`                                                | Security and privacy summary                    |
| `/report <user>`                                           | Report a user for abuse                         |
| `/export <chat> [--since YYYY-MM-DD] [--until YYYY-MM-DD]` | Export chat history (newest first, incremental) |
| `/export_list`                                             | List exported chats                             |
| `/quit`                                                    | Exit                                            |

`<user>` can be a numeric Telegram ID (e.g. `123456789`) or a username (e.g. `@example`).

### Non-interactive CLI

All commands output JSON to stdout, errors to stderr with exit code 1.

```bash
uv run python -m teleman me
uv run python -m teleman chats
uv run python -m teleman messages @example --limit 50
uv run python -m teleman send @example "hello"
uv run python -m teleman privacy
uv run python -m teleman lockdown
uv run python -m teleman sessions
uv run python -m teleman session-end <hash>
uv run python -m teleman settings [2fa|ttl|privacy|sessions|web]
uv run python -m teleman settings ttl 365
uv run python -m teleman export "Chat Name" --since 2025-08-01
uv run python -m teleman export-list
uv run python -m teleman links "Chat Name" --after 2026-01-01
```

## Export format

Exports live in `data/exports/<chat_id>/`:

```
data/exports/
  123456789/
    meta.json         # Chat metadata (title, type, participants)
    messages.jsonl    # One JSON object per line, chronological (oldest first)
    state.json        # Incremental export state: {newest_id, oldest_id, ...}
    topics.json       # Forum topics (if applicable)
```

### Export direction

Export always walks Telegram newest → oldest (backwards). The on-disk
`messages.jsonl` is kept chronological (oldest at the top, newest at the bottom):

- **Forward catch-up** on resume (messages with id > `state.newest_id`) is
  streamed to the end of the file.
- **Backfill** of older messages (bounded by `--since`) streams batches to
  `messages.backfill.jsonl` in iteration order (newest-first) as they arrive.
  On completion, the tmp file is stream-reversed in bounded memory (~64 KB
  blocks) and prepended to the top of `messages.jsonl` via an atomic
  temp-file rename. If the process is interrupted mid-backfill, the tmp
  file is preserved; re-running the same `sync --backfill --since DATE`
  resumes from the oldest message already buffered there.

Date filters:

- `--since YYYY-MM-DD` — stop walking backwards at this date (UTC).
- `--until YYYY-MM-DD` — filter out messages newer than this date.

Each message in `messages.jsonl`:

```json
{
  "id": 42,
  "sender_id": 123456,
  "sender_name": "Alice",
  "sender_username": "alice",
  "date": "2026-01-15T10:30:00+00:00",
  "text": "Hello world",
  "reply_to_msg_id": 41,
  "topic_id": null,
  "forward_from_id": null,
  "forward_from_name": null,
  "media": null,
  "entities": [{ "type": "bold", "offset": 0, "length": 5, "url": null }],
  "edit_date": null
}
```

## Analysis

Analysis skills operate on exported data. No Telegram connection needed.

```bash
uv run python -m analysis --scan                         # List exports
uv run python -m analysis --list                         # List skills
uv run python -m analysis <skill> <chat>                 # Run one skill
uv run python -m analysis --all <chat>                   # Run all skills
uv run python -m analysis.extract_user <chat> <user>     # Extract user messages
```

Skills: `overview`, `users`, `activity`, `media`, `tokens`.

Chat resolution accepts: chat_id, username, title substring, or path to `messages.jsonl`.

## Code Style

- Pydantic V2 models for all data structures
- `from __future__ import annotations` in all modules
- Ruff for linting and formatting — zero errors before committing

```bash
uv run ruff check teleman/ tests/
uv run ruff format --check teleman/ tests/
uv run pytest
```

## Architecture

```
teleman/                # Main package
  client.py             # Telethon client wrapper, auth, sessions
  cli.py                # Interactive REPL and command dispatch
  commands.py           # All command implementations
  config.py             # App configuration
  models.py             # Shared Pydantic models
  contacts.py           # Contact management
  messages.py           # Message fetching and sending
  privacy.py            # Privacy settings
  settings.py           # Security/privacy summary
  sessions.py           # Multi-account session handling
  proxy.py              # Per-account proxy config
  links.py              # Link extraction from exports
  report.py             # Abuse reporting
  export/               # Chat history export
    exporter.py         # Batch and incremental export
    models.py           # Export data models
    resolver.py         # Entity resolution
    storage.py          # JSONL file storage

analysis/               # Offline analysis engine
  __main__.py           # CLI runner
  loader.py             # JSONL loader and chat resolver
  registry.py           # Skill auto-discovery
  stats_overview.py     # Message counts, date range
  stats_users.py        # Per-user breakdown
  stats_activity.py     # Temporal patterns
  stats_media.py        # Media distribution
  stats_tokens.py       # LLM token estimates
  extract_user.py       # Single-user message extraction
```
