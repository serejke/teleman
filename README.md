# teleman

Your Telegram, from the terminal. Chat, export, analyze, profile — all without leaving the CLI.

Built on [Telethon](https://docs.telethon.dev/). Designed to be driven by humans and AI agents alike.

## What can it do?

**Talk to people**
Read messages, send messages, manage contacts — basic Telegram operations from your terminal. Interactive REPL or scriptable one-shot commands with JSON output.

**Lock down your account**
Audit privacy settings, active sessions, web authorizations, 2FA status. One command (`/lockdown`) sets everything to maximum privacy. Terminate suspicious sessions on the spot.

**Export chat history**
Full incremental export of any chat to structured JSONL. Re-run to pick up new messages without re-downloading everything. Forum topics, replies, forwards, media metadata, entities — all preserved.

**Analyze conversations**
Built-in analysis engine over exported chats: message stats, user rankings, activity patterns (by hour, day, date), media breakdown, LLM token estimates. All output is JSON — pipe it wherever you want.

**Profile participants**
Extract a user's full message history and feed it to an LLM for deep qualitative analysis: professional background, interests, communication style, best jokes. Works on any exported chat.

**Extract links**
Pull every URL from an exported chat, with date filters. Find that article someone shared three weeks ago.

## Two modes

**Interactive REPL** — launch and type commands:

```bash
uv run python -m teleman
```

**Non-interactive CLI** — scriptable, JSON output, perfect for AI agents:

```bash
uv run python -m teleman chats
uv run python -m teleman messages @example --limit 50
uv run python -m teleman export "My Group"
uv run python -m analysis --all "My Group"
```

## Analysis toolkit

After exporting a chat, run analysis skills against it:

```bash
# What's in the export?
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

That's it. You're in the REPL. Type `/chats` to see your conversations.

## More

See [README.dev.md](README.dev.md) for proxy setup, full command reference, export format, code style, and architecture.
