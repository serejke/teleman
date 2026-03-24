---
name: teleman
description: "Interact with Telegram via the teleman CLI — read chats, send messages, check privacy/sessions/settings, export history. Use when the user asks to do something on Telegram from this project."
argument-hint: "<command> [args] — e.g. 'chats', 'send @user hello', 'me'"
allowed-tools: Bash, Read
---

**Task: Execute teleman CLI commands on behalf of the user and interpret the JSON output.**

## Basics

- **Run**: `uv run python -m teleman <subcommand> [args]` from the project root
- **Account**: Pass `--account <name>` before the subcommand if the user specifies an account. If omitted and only one account exists, it's auto-selected. If multiple exist and none is specified, the CLI will prompt interactively — avoid this by always passing `--account` when you know the name.
- **Output**: All subcommands print **JSON to stdout**. Errors go to stderr as `{"error": "..."}` with exit code 1.
- **Peer identifiers**: Numeric ID (e.g. `12345`) or `@username`. Both work everywhere a peer/user is expected.

## Commands reference

### Read commands (safe, no side effects)

| Command                       | Description                                   | Example                                              |
| ----------------------------- | --------------------------------------------- | ---------------------------------------------------- |
| `me`                          | Current account info                          | `uv run python -m teleman me`                        |
| `chats`                       | List all chats with IDs, types, unread counts | `uv run python -m teleman chats`                     |
| `contacts`                    | List contacts                                 | `uv run python -m teleman contacts`                  |
| `messages <peer> [--limit N]` | Get last N messages (default 20)              | `uv run python -m teleman messages @durov --limit 5` |
| `privacy`                     | Show all privacy settings                     | `uv run python -m teleman privacy`                   |
| `sessions`                    | List active Telegram sessions                 | `uv run python -m teleman sessions`                  |
| `settings`                    | Full security/privacy overview                | `uv run python -m teleman settings`                  |
| `settings 2fa`                | 2FA status                                    | `uv run python -m teleman settings 2fa`              |
| `settings ttl`                | Account TTL                                   | `uv run python -m teleman settings ttl`              |
| `settings privacy`            | Privacy settings (same as `privacy`)          | `uv run python -m teleman settings privacy`          |
| `settings sessions`           | Sessions (same as `sessions`)                 | `uv run python -m teleman settings sessions`         |
| `settings web`                | Web authorizations                            | `uv run python -m teleman settings web`              |
| `web-sessions`                | List web authorizations                       | `uv run python -m teleman web-sessions`              |
| `export-list`                 | List chats available for export               | `uv run python -m teleman export-list`               |

### Write commands (have side effects)

| Command                     | Description                                  | Example                                                    |
| --------------------------- | -------------------------------------------- | ---------------------------------------------------------- |
| `send <peer> <text>`        | Send a message                               | `uv run python -m teleman send @user "hello"`              |
| `add <user>`                | Add a contact                                | `uv run python -m teleman add @username`                   |
| `privacy-set <key> <level>` | Set privacy (`everyone`/`contacts`/`nobody`) | `uv run python -m teleman privacy-set phone_number nobody` |
| `lockdown`                  | Set ALL privacy to `nobody`                  | `uv run python -m teleman lockdown`                        |
| `settings ttl <days>`       | Set account self-destruct TTL                | `uv run python -m teleman settings ttl 365`                |
| `session-end <hash>`        | Terminate a session                          | `uv run python -m teleman session-end 123456789`           |
| `web-end <hash>`            | Terminate a web session                      | `uv run python -m teleman web-end 123456789`               |
| `web-end-all`               | Terminate all web sessions                   | `uv run python -m teleman web-end-all`                     |
| `export <chat>`             | Export chat history (incremental)            | `uv run python -m teleman export "Chat Name"`              |

### Privacy keys for `privacy-set`

`phone_number`, `last_seen`, `profile_photo`, `bio`, `birthday`, `forwards`, `calls`, `groups`, `voice_messages`

## JSON output shapes

Key response structures (all fields present, nulls explicit):

```
me              → {id, first_name, last_name, username, phone, premium}
chats           → {chats: [{id, type, username, unread_count}, ...]}
contacts        → {contacts: [{id, first_name, last_name, username, phone, premium}, ...]}
messages        → {peer_id, messages: [{id, sender_id, chat_id, text, date, out}, ...]}
send            → {message: {id, sender_id, chat_id, text, date, out}}
add             → {user: {id, first_name, ...}}
privacy         → {rules: [{key, label, level, error}, ...]}
privacy-set     → {rules: [{key, label, level, error}]}
lockdown        → {rules: [{key, label, level, error}, ...]}
sessions        → {sessions: [{hash, current, device_model, platform, system_version, app_name, app_version, ip, country, date_created, date_active, official_app}, ...]}
session-end     → {hash, device_model}
settings        → {two_factor: {enabled, has_recovery_email}, account_ttl: {days}, privacy: [...], sessions: [...], web_sessions: [...]}
web-sessions    → {sessions: [{hash, domain, browser, platform, ip, region, date_created, date_active, bot_name}, ...]}
web-end         → {hash, domain}
web-end-all     → {}
export-list     → {chats: [{chat_id, title, type, username}, ...]}
export          → {title, message_count, incremental}
```

## How to handle `$ARGUMENTS`

1. Parse the user's request from `$ARGUMENTS`.
2. Map it to the appropriate subcommand above.
3. Run the command via Bash, capture stdout.
4. Parse the JSON and present a concise human-readable summary to the user.
5. For write commands, confirm the action was successful. For reads, summarize the key data points.
6. If the command fails (exit code 1), read stderr for the error JSON and report it.

## Important

- **Never run `repl`** — that starts an interactive session which cannot be driven non-interactively.
- When sending messages, always quote the text argument to preserve spaces.
- Dates in JSON are ISO 8601 UTC.
- The `messages` command returns newest-first order.
