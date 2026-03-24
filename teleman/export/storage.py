from __future__ import annotations

from pathlib import Path

from teleman.export.models import ChatMeta, ExportedMessage, ExportState, ForumTopic

DATA_DIR_NAME = "data"
EXPORTS_DIR_NAME = "exports"
META_FILE = "meta.json"
MESSAGES_FILE = "messages.jsonl"
STATE_FILE = "state.json"
TOPICS_FILE = "topics.json"


def get_data_dir() -> Path:
    return Path(__file__).resolve().parents[2] / DATA_DIR_NAME


def get_chat_dir(data_dir: Path, chat_id: int) -> Path:
    chat_dir = data_dir / EXPORTS_DIR_NAME / str(chat_id)
    chat_dir.mkdir(parents=True, exist_ok=True)
    return chat_dir


def write_meta(chat_dir: Path, meta: ChatMeta) -> None:
    path = chat_dir / META_FILE
    path.write_text(meta.model_dump_json(indent=2) + "\n")


def read_meta(chat_dir: Path) -> ChatMeta | None:
    path = chat_dir / META_FILE
    if not path.exists():
        return None
    return ChatMeta.model_validate_json(path.read_text())


def write_state(chat_dir: Path, state: ExportState) -> None:
    path = chat_dir / STATE_FILE
    path.write_text(state.model_dump_json(indent=2) + "\n")


def read_state(chat_dir: Path) -> ExportState | None:
    path = chat_dir / STATE_FILE
    if not path.exists():
        return None
    return ExportState.model_validate_json(path.read_text())


def write_topics(chat_dir: Path, topics: list[ForumTopic]) -> None:
    path = chat_dir / TOPICS_FILE
    import json

    data = [t.model_dump() for t in topics]
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n")


def append_messages(chat_dir: Path, messages: list[ExportedMessage]) -> None:
    if not messages:
        return
    path = chat_dir / MESSAGES_FILE
    with path.open("a") as f:
        for msg in messages:
            f.write(msg.model_dump_json() + "\n")
