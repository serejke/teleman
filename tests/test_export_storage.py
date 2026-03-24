from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path

from teleman.export.models import ChatMeta, ExportedMessage, ExportState
from teleman.export.storage import (
    append_messages,
    get_chat_dir,
    read_meta,
    read_state,
    write_meta,
    write_state,
)


class TestGetChatDir:
    def test_creates_directory(self, tmp_path: Path) -> None:
        chat_dir = get_chat_dir(tmp_path, -1001234567)
        assert chat_dir.exists()
        assert chat_dir == tmp_path / "exports" / "-1001234567"

    def test_idempotent(self, tmp_path: Path) -> None:
        dir1 = get_chat_dir(tmp_path, 123)
        dir2 = get_chat_dir(tmp_path, 123)
        assert dir1 == dir2


class TestMetaIO:
    def test_roundtrip(self, tmp_path: Path) -> None:
        now = datetime(2026, 3, 24, 12, 0, tzinfo=UTC)
        meta = ChatMeta(
            chat_id=-1001234567,
            title="Test Group",
            type="group",
            megagroup=True,
            participants_count=42,
            exported_at=now,
            updated_at=now,
        )
        write_meta(tmp_path, meta)
        restored = read_meta(tmp_path)
        assert restored is not None
        assert restored.chat_id == meta.chat_id
        assert restored.title == meta.title

    def test_read_nonexistent(self, tmp_path: Path) -> None:
        assert read_meta(tmp_path) is None


class TestStateIO:
    def test_roundtrip(self, tmp_path: Path) -> None:
        now = datetime(2026, 3, 24, 16, 0, tzinfo=UTC)
        state = ExportState(last_message_id=1042, last_export_date=now, total_messages=1042)
        write_state(tmp_path, state)
        restored = read_state(tmp_path)
        assert restored is not None
        assert restored.last_message_id == 1042
        assert restored.total_messages == 1042

    def test_read_nonexistent(self, tmp_path: Path) -> None:
        assert read_state(tmp_path) is None


class TestAppendMessages:
    def _make_msg(self, msg_id: int, text: str) -> ExportedMessage:
        return ExportedMessage(
            id=msg_id,
            sender_id=111,
            sender_name="Alice",
            date=datetime(2026, 1, 15, 10, 30, tzinfo=UTC),
            text=text,
        )

    def test_append_creates_file(self, tmp_path: Path) -> None:
        messages = [self._make_msg(1, "Hello"), self._make_msg(2, "World")]
        append_messages(tmp_path, messages)
        path = tmp_path / "messages.jsonl"
        assert path.exists()
        lines = path.read_text().strip().split("\n")
        assert len(lines) == 2
        assert json.loads(lines[0])["text"] == "Hello"
        assert json.loads(lines[1])["text"] == "World"

    def test_append_to_existing(self, tmp_path: Path) -> None:
        first_batch = [self._make_msg(1, "First")]
        second_batch = [self._make_msg(2, "Second"), self._make_msg(3, "Third")]
        append_messages(tmp_path, first_batch)
        append_messages(tmp_path, second_batch)
        path = tmp_path / "messages.jsonl"
        lines = path.read_text().strip().split("\n")
        assert len(lines) == 3
        assert json.loads(lines[0])["id"] == 1
        assert json.loads(lines[2])["id"] == 3

    def test_empty_list_noop(self, tmp_path: Path) -> None:
        append_messages(tmp_path, [])
        path = tmp_path / "messages.jsonl"
        assert not path.exists()
