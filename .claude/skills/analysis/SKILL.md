---
name: analysis
description: "Analyze exported Telegram chats. Use when the user asks to: list/scan/find exported chats, check what's been exported, get chat statistics, see top users, activity patterns, media breakdown, token counts, or any question about exported chat data."
argument-hint: "<question or command> — e.g. 'scan chats', 'top users in <chat>', 'activity patterns for <chat>', 'overview of <chat>'"
allowed-tools: Bash, Read
---

**Task: Answer user questions about exported Telegram chats by running analysis skills and interpreting the JSON output.**

## Basics

- **Run**: `uv run python -m analysis <subcommand> [args]` from the project root
- **Output**: All commands print **JSON to stdout**. Errors go to stderr with exit code 1.
- **Chat resolution**: Chats can be referenced by chat_id, username, title substring, or full path. The CLI resolves automatically.
- **Exports location**: `data/exports/` — each subdirectory is a chat with `meta.json` + `messages.jsonl`.

## Commands

### Discovery

| Command  | Description                                              | Example                            |
| -------- | -------------------------------------------------------- | ---------------------------------- |
| `--scan` | List all exported chats with metadata and message counts | `uv run python -m analysis --scan` |
| `--list` | List available analysis skills                           | `uv run python -m analysis --list` |

### Running skills

| Command          | Description              | Example                                     |
| ---------------- | ------------------------ | ------------------------------------------- |
| `<skill> <chat>` | Run one skill on a chat  | `uv run python -m analysis overview <chat>` |
| `--all <chat>`   | Run all skills on a chat | `uv run python -m analysis --all <chat>`    |

### Available skills

| Skill      | What it computes                                                                                      |
| ---------- | ----------------------------------------------------------------------------------------------------- |
| `overview` | Total messages, text/media counts, forwards, replies, edits, unique senders, date range               |
| `users`    | Top users ranked by messages, characters, media, replies, forwards, avg message length, active period |
| `activity` | Messages by date, hour of day, day of week; most active date/hour/day                                 |
| `media`    | Media type distribution, top media senders, file size stats                                           |
| `tokens`   | LLM token estimates (text-only, structured, daily breakdown)                                          |

## JSON output shapes

```
--scan      → {chats: [{chat_id, title, type, username, megagroup, participants_count, message_count, export_dir}, ...]}
overview    → {total_messages, total_messages_with_text, total_messages_with_media, total_symbols, total_forwards, total_replies, total_edits, unique_senders, date_range: {first, last}}
users       → {total_unique_senders, top_n, users: [{sender_name, messages, text_messages, symbols, media, replies, forwards, avg_message_length, first_date, last_date}, ...]}
activity    → {by_date: [{date, messages}], by_hour: [{hour, messages}], by_day_of_week: [{day, day_index, messages}], most_active_date, most_active_hour, most_active_day}
media       → {total_media_messages, by_type: [{type, count}], top_senders: [{sender_name, media_count}], file_sizes: {total_bytes, total_mb, count_with_size, avg_bytes}}
tokens      → {encoding, note, text_only_tokens, structured_tokens, total_messages, avg_tokens_per_message, by_date: [{date, messages, tokens}]}
```

## How to handle `$ARGUMENTS`

1. If the user asks to discover/list/scan chats, run `--scan`.
2. If the user asks a specific question, determine which skill(s) answer it:
   - "who talks the most" / "top users" / "most active people" → `users`
   - "when is the chat most active" / "activity patterns" → `activity`
   - "how many messages" / "overview" / "summary" → `overview`
   - "what media" / "photos" / "files" → `media`
   - "how many tokens" / "context window" / "LLM cost" → `tokens`
   - General dashboard / "tell me about this chat" → `--all`
3. Run the command via Bash, capture stdout, parse JSON.
4. Present a concise, human-readable summary. Highlight the most interesting findings — don't just dump raw numbers.
5. For `users`, focus on the top contributors and notable patterns (who writes the longest messages, who shares the most media, etc.).
6. For `activity`, highlight peaks and patterns (busiest day, most active hours, weekend vs weekday).
7. Combine multiple skills if the question spans them.

## Writing custom analysis

The built-in skills are just common projections — not a complete list. If the user's question isn't answered by existing skills, **write a custom Python script** that loads the data and computes what's needed. Follow these conventions:

- Import `from analysis.loader import Message, load_messages, resolve_chat` to load data.
- `Message` is a Pydantic V2 model with fields: `id`, `sender_id`, `sender_name`, `date`, `text`, `reply_to_msg_id`, `forward_from_id`, `forward_from_name`, `media` (with `.type`, `.file_name`, `.mime_type`, `.size`), `entities`, `edit_date`.
- Output JSON to stdout. Define Pydantic result models for the output.
- Run via `uv run python <script> <chat>` using `resolve_chat(sys.argv[1])` for chat resolution.
- Examples of custom analyses: reply graphs, conversation threads, keyword frequency, sentiment over time, link extraction, user interaction pairs, message length distributions, time-to-reply stats.

If a custom analysis turns out to be broadly useful, promote it to a proper `stats_*.py` skill module with `NAME`, `DESCRIPTION`, and `compute()` so it becomes auto-discoverable.

## Important

- Always run `--scan` first if you don't know which chats are available.
- Chat data must be exported first via `/teleman export <chat>` before analysis is possible.
- The `tokens` skill is slower than others (runs tiktoken encoding). Only run it when token counts are specifically asked for or as part of `--all`.
- All dates in output are ISO format (YYYY-MM-DD). Times in messages are UTC.
