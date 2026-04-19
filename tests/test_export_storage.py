from __future__ import annotations

import json
from datetime import UTC, datetime
from typing import TYPE_CHECKING

from teleman.export.models import ChatMeta, Checkpoint, ExportedMessage, ExportState
from teleman.export.storage import (
    _iter_lines_reverse,
    append_backfill,
    append_checkpoint,
    append_messages,
    finalize_backfill,
    get_chat_dir,
    list_tracked_chat_dirs,
    prepend_messages,
    read_backfill_head,
    read_backfill_tail,
    read_checkpoints,
    read_meta,
    read_state,
    write_meta,
    write_state,
)

if TYPE_CHECKING:
    from pathlib import Path


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
        state = ExportState(newest_id=1042, oldest_id=1, last_sync_date=now, total_messages=1042)
        write_state(tmp_path, state)
        restored = read_state(tmp_path)
        assert restored is not None
        assert restored.newest_id == 1042
        assert restored.oldest_id == 1
        assert restored.total_messages == 1042
        assert restored.tracked is True

    def test_read_nonexistent(self, tmp_path: Path) -> None:
        assert read_state(tmp_path) is None


class TestCheckpointIO:
    def test_append_and_read(self, tmp_path: Path) -> None:
        now = datetime(2026, 3, 24, 16, 0, tzinfo=UTC)
        cp1 = Checkpoint(id=now, created_at=now, newest_id=100, prev_newest_id=0, delta_count=100)
        later = datetime(2026, 3, 25, 16, 0, tzinfo=UTC)
        cp2 = Checkpoint(
            id=later, created_at=later, newest_id=250, prev_newest_id=100, delta_count=150
        )

        append_checkpoint(tmp_path, cp1)
        append_checkpoint(tmp_path, cp2)
        restored = read_checkpoints(tmp_path)

        assert len(restored) == 2
        assert restored[0].newest_id == 100
        assert restored[1].newest_id == 250
        assert restored[1].prev_newest_id == 100

    def test_read_nonexistent(self, tmp_path: Path) -> None:
        assert read_checkpoints(tmp_path) == []


class TestListTrackedChatDirs:
    def test_filters_by_tracked_flag(self, tmp_path: Path) -> None:
        exports = tmp_path / "exports"
        exports.mkdir()
        now = datetime(2026, 3, 24, 16, 0, tzinfo=UTC)

        tracked_dir = exports / "111"
        tracked_dir.mkdir()
        write_state(
            tracked_dir,
            ExportState(
                newest_id=5, oldest_id=1, last_sync_date=now, total_messages=5, tracked=True
            ),
        )

        untracked_dir = exports / "222"
        untracked_dir.mkdir()
        write_state(
            untracked_dir,
            ExportState(
                newest_id=5, oldest_id=1, last_sync_date=now, total_messages=5, tracked=False
            ),
        )

        empty_dir = exports / "333"
        empty_dir.mkdir()

        result = list_tracked_chat_dirs(tmp_path)
        assert result == [tracked_dir]


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


class TestPrependMessages:
    def _make_msg(self, msg_id: int, text: str) -> ExportedMessage:
        return ExportedMessage(
            id=msg_id,
            sender_id=111,
            sender_name="Alice",
            date=datetime(2026, 1, 15, 10, 30, tzinfo=UTC),
            text=text,
        )

    def test_prepend_creates_file(self, tmp_path: Path) -> None:
        prepend_messages(tmp_path, [self._make_msg(1, "Hello")])
        path = tmp_path / "messages.jsonl"
        assert path.exists()
        line = path.read_text().strip()
        assert json.loads(line)["text"] == "Hello"

    def test_prepend_before_existing(self, tmp_path: Path) -> None:
        append_messages(tmp_path, [self._make_msg(10, "later"), self._make_msg(11, "latest")])
        prepend_messages(tmp_path, [self._make_msg(1, "first"), self._make_msg(2, "second")])
        lines = (tmp_path / "messages.jsonl").read_text().strip().split("\n")
        assert [json.loads(line)["id"] for line in lines] == [1, 2, 10, 11]

    def test_empty_noop(self, tmp_path: Path) -> None:
        prepend_messages(tmp_path, [])
        assert not (tmp_path / "messages.jsonl").exists()


class TestIterLinesReverse:
    def test_simple(self, tmp_path: Path) -> None:
        path = tmp_path / "f.txt"
        path.write_bytes(b"a\nb\nc\n")
        assert [line.decode() for line in _iter_lines_reverse(path)] == ["c", "b", "a"]

    def test_no_trailing_newline(self, tmp_path: Path) -> None:
        path = tmp_path / "f.txt"
        path.write_bytes(b"a\nb\nc")
        assert [line.decode() for line in _iter_lines_reverse(path)] == ["c", "b", "a"]

    def test_single_line(self, tmp_path: Path) -> None:
        path = tmp_path / "f.txt"
        path.write_bytes(b"only\n")
        assert [line.decode() for line in _iter_lines_reverse(path)] == ["only"]

    def test_small_block_size(self, tmp_path: Path) -> None:
        path = tmp_path / "f.txt"
        path.write_bytes(b"alpha\nbravo\ncharlie\ndelta\n")
        # Block size smaller than any line forces multi-chunk reconstitution.
        assert [line.decode() for line in _iter_lines_reverse(path, block_size=4)] == [
            "delta",
            "charlie",
            "bravo",
            "alpha",
        ]

    def test_empty_file(self, tmp_path: Path) -> None:
        path = tmp_path / "f.txt"
        path.write_bytes(b"")
        assert list(_iter_lines_reverse(path)) == []


class TestBackfillStreaming:
    def _make_msg(self, msg_id: int, hour: int) -> ExportedMessage:
        return ExportedMessage(
            id=msg_id,
            sender_id=1,
            sender_name="A",
            date=datetime(2026, 1, 15, hour, 0, tzinfo=UTC),
            text=f"m{msg_id}",
        )

    def test_append_and_finalize_no_existing(self, tmp_path: Path) -> None:
        # iteration order is newest→oldest, so tmp lines are in descending id
        append_backfill(tmp_path, [self._make_msg(30, 12), self._make_msg(29, 11)])
        append_backfill(tmp_path, [self._make_msg(28, 10), self._make_msg(27, 9)])

        assert read_backfill_head(tmp_path) == (30, datetime(2026, 1, 15, 12, 0, tzinfo=UTC))
        assert read_backfill_tail(tmp_path) == (27, datetime(2026, 1, 15, 9, 0, tzinfo=UTC))

        count = finalize_backfill(tmp_path)
        assert count == 4

        lines = (tmp_path / "messages.jsonl").read_text().strip().split("\n")
        assert [json.loads(line)["id"] for line in lines] == [27, 28, 29, 30]
        assert not (tmp_path / "messages.backfill.jsonl").exists()

    def test_finalize_prepends_to_existing(self, tmp_path: Path) -> None:
        # Existing chronological file has newer messages.
        append_messages(tmp_path, [self._make_msg(100, 20), self._make_msg(101, 21)])
        # Backfill pulls older ones (newest-first into tmp).
        append_backfill(tmp_path, [self._make_msg(50, 10), self._make_msg(49, 9)])

        finalize_backfill(tmp_path)

        lines = (tmp_path / "messages.jsonl").read_text().strip().split("\n")
        assert [json.loads(line)["id"] for line in lines] == [49, 50, 100, 101]

    def test_resume_across_runs(self, tmp_path: Path) -> None:
        # First "run" wrote two batches and crashed.
        append_backfill(tmp_path, [self._make_msg(30, 12), self._make_msg(29, 11)])
        append_backfill(tmp_path, [self._make_msg(28, 10)])

        # A resumed run sees the tail as the resume point and appends more.
        assert read_backfill_tail(tmp_path) == (28, datetime(2026, 1, 15, 10, 0, tzinfo=UTC))
        append_backfill(tmp_path, [self._make_msg(27, 9), self._make_msg(26, 8)])

        finalize_backfill(tmp_path)
        lines = (tmp_path / "messages.jsonl").read_text().strip().split("\n")
        assert [json.loads(line)["id"] for line in lines] == [26, 27, 28, 29, 30]

    def test_finalize_noop_on_missing_tmp(self, tmp_path: Path) -> None:
        assert finalize_backfill(tmp_path) == 0
