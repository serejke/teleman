from __future__ import annotations

import json
import shutil
from pathlib import Path

from teleman.export.models import ChatMeta, Checkpoint, ExportedMessage, ExportState, ForumTopic

DATA_DIR_NAME = "data"
EXPORTS_DIR_NAME = "exports"
META_FILE = "meta.json"
MESSAGES_FILE = "messages.jsonl"
STATE_FILE = "state.json"
TOPICS_FILE = "topics.json"
CHECKPOINTS_FILE = "checkpoints.jsonl"


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
    data = [t.model_dump() for t in topics]
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n")


def append_messages(chat_dir: Path, messages: list[ExportedMessage]) -> None:
    if not messages:
        return
    path = chat_dir / MESSAGES_FILE
    with path.open("a") as f:
        for msg in messages:
            f.write(msg.model_dump_json() + "\n")


def append_checkpoint(chat_dir: Path, checkpoint: Checkpoint) -> None:
    path = chat_dir / CHECKPOINTS_FILE
    with path.open("a") as f:
        f.write(checkpoint.model_dump_json() + "\n")


def read_checkpoints(chat_dir: Path) -> list[Checkpoint]:
    path = chat_dir / CHECKPOINTS_FILE
    if not path.exists():
        return []
    checkpoints: list[Checkpoint] = []
    with path.open() as f:
        for line in f:
            line = line.strip()
            if line:
                checkpoints.append(Checkpoint.model_validate_json(line))
    return checkpoints


def list_tracked_chat_dirs(data_dir: Path) -> list[Path]:
    """List chat dirs whose state.json marks them as tracked."""
    exports_dir = data_dir / EXPORTS_DIR_NAME
    if not exports_dir.exists():
        return []
    tracked: list[Path] = []
    for chat_dir in exports_dir.iterdir():
        if not chat_dir.is_dir():
            continue
        state = read_state(chat_dir)
        if state is not None and state.tracked:
            tracked.append(chat_dir)
    return tracked


def prepend_messages(chat_dir: Path, messages: list[ExportedMessage]) -> None:
    """Prepend messages (in chronological order) to the start of messages.jsonl.

    Writes to a temp file and atomically renames, so partial failures don't
    corrupt the existing file.
    """
    if not messages:
        return
    path = chat_dir / MESSAGES_FILE
    tmp = chat_dir / (MESSAGES_FILE + ".tmp")
    with tmp.open("w") as out:
        for msg in messages:
            out.write(msg.model_dump_json() + "\n")
        if path.exists():
            with path.open("r") as existing:
                shutil.copyfileobj(existing, out)
    tmp.replace(path)
