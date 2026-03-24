"""Reusable loader for exported Telegram chat JSONL files."""

from __future__ import annotations

import json
from pathlib import Path

from pydantic import BaseModel

from teleman.export.models import ChatMeta, ExportedMessage

# Re-export for convenience — all analysis modules import from here.
Message = ExportedMessage


class ChatSummary(BaseModel):
    chat_id: int
    title: str
    type: str
    username: str | None
    megagroup: bool
    participants_count: int | None
    message_count: int
    export_dir: str


class ScanResult(BaseModel):
    chats: list[ChatSummary]


EXPORTS_DIR = Path("data/exports")


def resolve_chat(query: str) -> Path:
    """Resolve a chat query to a messages.jsonl path.

    Accepts: chat_id, username, title substring, or full path to messages.jsonl.
    """
    # Direct path
    p = Path(query)
    if p.exists():
        return p if p.is_file() else p / "messages.jsonl"

    # Search exports dir
    if not EXPORTS_DIR.exists():
        raise FileNotFoundError(f"Exports directory not found: {EXPORTS_DIR}")

    # Exact chat_id match
    candidate = EXPORTS_DIR / query / "messages.jsonl"
    if candidate.exists():
        return candidate

    # Fuzzy match on meta.json fields
    query_lower = query.lower()
    for child in sorted(EXPORTS_DIR.iterdir()):
        meta_file = child / "meta.json"
        if not meta_file.exists():
            continue
        meta = ChatMeta.model_validate(json.loads(meta_file.read_text(encoding="utf-8")))
        if (meta.username and meta.username.lower() == query_lower) or query_lower in meta.title.lower():
            return child / "messages.jsonl"

    raise FileNotFoundError(f"No chat matching {query!r} in {EXPORTS_DIR}")


def load_messages(path: str | Path) -> list[Message]:
    """Load messages from a JSONL file, returning typed Message objects."""
    path = Path(path)
    messages: list[Message] = []
    with path.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            messages.append(Message.model_validate(json.loads(line)))
    return messages


def load_meta(export_dir: str | Path) -> ChatMeta:
    """Load chat metadata from meta.json in an export directory."""
    path = Path(export_dir) / "meta.json"
    return ChatMeta.model_validate(json.loads(path.read_text(encoding="utf-8")))


def _count_lines(path: Path) -> int:
    count = 0
    with path.open("r", encoding="utf-8") as f:
        for line in f:
            if line.strip():
                count += 1
    return count


def scan_exports(exports_dir: str | Path) -> ScanResult:
    """Scan an exports directory and return metadata + message count for each chat."""
    exports_dir = Path(exports_dir)
    chats: list[ChatSummary] = []
    for child in sorted(exports_dir.iterdir()):
        meta_file = child / "meta.json"
        messages_file = child / "messages.jsonl"
        if not meta_file.exists() or not messages_file.exists():
            continue
        meta = ChatMeta.model_validate(json.loads(meta_file.read_text(encoding="utf-8")))
        chats.append(
            ChatSummary(
                chat_id=meta.chat_id,
                title=meta.title,
                type=meta.type,
                username=meta.username,
                megagroup=meta.megagroup,
                participants_count=meta.participants_count,
                message_count=_count_lines(messages_file),
                export_dir=str(child),
            )
        )
    return ScanResult(chats=chats)
