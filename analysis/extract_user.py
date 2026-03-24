"""Extract all messages from a specific user in an exported chat.

Usage:
    python -m analysis.extract_user <chat> <user_name> [--format text|jsonl]

Outputs chronological messages as human-readable text (default) or JSONL.
Text format is designed for LLM context ingestion — includes timestamps, reply context, and media info.
"""

from __future__ import annotations

import json
import sys
from analysis.loader import Message, load_messages, resolve_chat


def _format_message_text(msg: Message) -> str:
    """Format a single message as a human-readable line."""
    ts = msg.date.strftime("%Y-%m-%d %H:%M")
    parts: list[str] = [f"[{ts}]"]

    if msg.forward_from_name:
        parts.append(f"[fwd from {msg.forward_from_name}]")

    if msg.reply_to_msg_id:
        parts.append(f"[reply to #{msg.reply_to_msg_id}]")

    if msg.media:
        media_desc = msg.media.type
        if msg.media.file_name:
            media_desc += f": {msg.media.file_name}"
        parts.append(f"[{media_desc}]")

    if msg.text:
        parts.append(msg.text)
    elif not msg.media:
        parts.append("[empty]")

    if msg.edit_date:
        parts.append("(edited)")

    return " ".join(parts)


def extract_user_messages(
    messages: list[Message], user_query: str
) -> list[Message]:
    """Filter messages by sender name or username (case-insensitive).

    Supports: exact name, substring of name, or @username.
    """
    query = user_query.lower().lstrip("@")
    # Try username match first (exact)
    by_username = [m for m in messages if m.sender_username and m.sender_username.lower() == query]
    if by_username:
        return by_username
    # Try exact name match
    exact = [m for m in messages if m.sender_name and m.sender_name.lower() == query]
    if exact:
        return exact
    # Fall back to substring of name
    return [m for m in messages if m.sender_name and query in m.sender_name.lower()]


def main() -> None:
    if len(sys.argv) < 3:
        print("Usage: python -m analysis.extract_user <chat> <user_name> [--format text|jsonl]", file=sys.stderr)
        sys.exit(1)

    chat_query = sys.argv[1]
    user_name = sys.argv[2]
    fmt = "text"
    if "--format" in sys.argv:
        idx = sys.argv.index("--format")
        if idx + 1 < len(sys.argv):
            fmt = sys.argv[idx + 1]

    path = resolve_chat(chat_query)
    messages = load_messages(path)
    user_msgs = extract_user_messages(messages, user_name)

    if not user_msgs:
        # List available senders to help
        senders = sorted({m.sender_name for m in messages if m.sender_name})
        print(f"No messages found for {user_name!r}.", file=sys.stderr)
        print(f"Available senders: {', '.join(senders)}", file=sys.stderr)
        sys.exit(1)

    sender = user_msgs[0].sender_name

    if fmt == "jsonl":
        for msg in user_msgs:
            print(json.dumps(msg.model_dump(), ensure_ascii=False, default=str))
    else:
        # Header
        first = user_msgs[0].date.strftime("%Y-%m-%d")
        last = user_msgs[-1].date.strftime("%Y-%m-%d")
        print(f"=== {sender} — {len(user_msgs)} messages ({first} to {last}) ===\n")
        for msg in user_msgs:
            print(_format_message_text(msg))


if __name__ == "__main__":
    main()
