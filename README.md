# teleman

Sync your Telegram chats to disk, then analyze and profile them from the terminal.

Built on [Telethon](https://docs.telethon.dev/). Designed to be driven by humans and AI agents alike.

## What can it do?

**Sync chat history to JSONL**
Pull any chat to structured JSONL with a checkpointed, incremental sync. Re-run to catch up on new messages without re-downloading anything — checkpoints track exactly what's been seen. `--since DATE` walks backwards to fill older history. Forum topics, replies, forwards, media metadata, and entities are all preserved. Track a set of chats and sync them all in one command.

**Analyze conversations**
Built-in analysis engine over synced chats: message stats, user rankings, activity patterns (by hour, day, date), media breakdown, LLM token estimates. All output is JSON — pipe it wherever you want.

**Profile participants**
Extract a user's full message history and feed it to an LLM for deep qualitative analysis: professional background, interests, communication style, best jokes. Works on any synced chat.

**Extract links**
Pull every URL from a synced chat, with date filters. Find that article someone shared three weeks ago.

**Lock down your account**
Audit privacy settings, active sessions, web authorizations, 2FA status. One command (`lockdown`) sets everything to maximum privacy. Terminate suspicious sessions on the spot.

**Read and send messages**
Basic Telegram operations from your terminal — read messages, send messages, manage contacts. Useful for scripting, bots, and day-to-day CLI workflows.

## Syncing chats

The first-ever sync of a chat must be bounded by `--since` (or explicitly `--all-history`) — a safety guard against accidental full-history fetches. After that, re-running `sync` is a cheap forward catch-up.

```bash
# First sync: pull messages from this date forward
uv run python -m teleman sync "My Group" --since 2025-08-01

# Re-run any time to catch up on new messages (checkpointed, incremental)
uv run python -m teleman sync "My Group"

# Walk further back in time
uv run python -m teleman sync "My Group" --since 2024-01-01

# Sync every tracked chat at once (forward catch-up only)
uv run python -m teleman sync --all

# Manage the tracked set
uv run python -m teleman track "Another Chat"
uv run python -m teleman untrack "Another Chat"
uv run python -m teleman tracked

# Inspect the checkpoint history for a chat
uv run python -m teleman checkpoints "My Group"

# List chats available to sync
uv run python -m teleman export-list
```

Synced data lives in `data/exports/<chat_id>/` as `messages.jsonl` plus metadata and checkpoints. See [README.dev.md](README.dev.md) for the on-disk format and sync internals.

## Analysis toolkit

After syncing a chat, run analysis skills against it:

```bash
# What's been synced?
uv run python -m analysis --scan

# Full dashboard
uv run python -m analysis --all "My Group"

# Individual skills
uv run python -m analysis overview "My Group"
uv run python -m analysis users "My Group"
uv run python -m analysis activity "My Group"
uv run python -m analysis media "My Group"
uv run python -m analysis tokens "My Group"

# Extract a single user's messages
uv run python -m analysis.extract_user "My Group" @username
```

## Two modes

**Non-interactive CLI** — scriptable, JSON output, perfect for AI agents:

```bash
uv run python -m teleman chats
uv run python -m teleman sync "My Group" --since 2025-08-01
uv run python -m teleman sync --all
uv run python -m analysis --all "My Group"
uv run python -m teleman messages @example --limit 50
```

**Interactive REPL** — launch and type commands:

```bash
uv run python -m teleman
```

## Getting started

Requires [uv](https://docs.astral.sh/uv/).

```bash
uv sync
```

### 1. Get Telegram API credentials

Go to [my.telegram.org](https://my.telegram.org), log in with your phone number, and create an app. You'll get an `app_id` and `app_hash`.

### 2. Create an account file

```bash
mkdir -p accounts
cat > accounts/15551234567.json << 'EOF'
{
  "app_id": 12345,
  "app_hash": "your_api_hash",
  "phone": "+15551234567"
}
EOF
```

Replace with your actual credentials and phone number.

### 3. Log in

```bash
uv run python -m teleman
```

On first run, Telegram sends a login code to your phone. Enter it in the terminal — teleman saves a session file so you only do this once.

That's it. You're in the REPL. Type `/chats` to see your conversations, then sync one to disk with `sync "<chat>" --since 2025-08-01`.

## More

See [README.dev.md](README.dev.md) for proxy setup, full command reference, sync internals, code style, and architecture.
