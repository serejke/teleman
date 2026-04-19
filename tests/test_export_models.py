from __future__ import annotations

from datetime import UTC, datetime
from types import SimpleNamespace

from teleman.export.models import ChatMeta, Checkpoint, ExportedMessage, ExportState


class TestChatMetaFromTelethon:
    def test_group(self) -> None:
        now = datetime(2026, 3, 24, 12, 0, tzinfo=UTC)
        obj = SimpleNamespace(
            id=-1001234567,
            title="Portuguese School",
            username=None,
            megagroup=True,
            broadcast=False,
            participants_count=42,
        )
        meta = ChatMeta.from_telethon(obj, now=now)
        assert meta.chat_id == -1001234567
        assert meta.title == "Portuguese School"
        assert meta.type == "group"
        assert meta.megagroup is True
        assert meta.participants_count == 42
        assert meta.exported_at == now

    def test_channel(self) -> None:
        now = datetime(2026, 3, 24, 12, 0, tzinfo=UTC)
        obj = SimpleNamespace(
            id=-1009999999,
            title="News",
            username="news",
            megagroup=False,
            broadcast=True,
            participants_count=1000,
        )
        meta = ChatMeta.from_telethon(obj, now=now)
        assert meta.type == "channel"
        assert meta.username == "news"

    def test_user(self) -> None:
        now = datetime(2026, 3, 24, 12, 0, tzinfo=UTC)
        obj = SimpleNamespace(
            id=111222,
            first_name="Alice",
            username="alice",
        )
        meta = ChatMeta.from_telethon(obj, now=now)
        assert meta.type == "user"
        assert meta.title == "Alice"


class TestExportedMessageFromTelethon:
    def test_basic_message(self) -> None:
        date = datetime(2026, 1, 15, 10, 30, tzinfo=UTC)
        sender = SimpleNamespace(first_name="Alice", last_name="Smith")
        obj = SimpleNamespace(
            id=100,
            sender_id=111,
            sender=sender,
            date=date,
            text="Bom dia!",
            reply_to=None,
            forward=None,
            media=None,
            edit_date=None,
        )
        msg = ExportedMessage.from_telethon(obj)
        assert msg.id == 100
        assert msg.sender_id == 111
        assert msg.sender_name == "Alice Smith"
        assert msg.text == "Bom dia!"
        assert msg.reply_to_msg_id is None
        assert msg.media is None

    def test_reply_message(self) -> None:
        date = datetime(2026, 1, 15, 10, 31, tzinfo=UTC)
        obj = SimpleNamespace(
            id=101,
            sender_id=222,
            sender=SimpleNamespace(first_name="Bob", last_name=None),
            date=date,
            text="Olá!",
            reply_to=SimpleNamespace(reply_to_msg_id=100),
            forward=None,
            media=None,
            edit_date=None,
        )
        msg = ExportedMessage.from_telethon(obj)
        assert msg.reply_to_msg_id == 100
        assert msg.sender_name == "Bob"

    def test_forwarded_message(self) -> None:
        date = datetime(2026, 1, 15, 10, 32, tzinfo=UTC)
        obj = SimpleNamespace(
            id=102,
            sender_id=333,
            sender=SimpleNamespace(first_name="Carlos"),
            date=date,
            text="Forwarded text",
            reply_to=None,
            forward=SimpleNamespace(
                from_id=SimpleNamespace(user_id=444, channel_id=None),
                from_name="Original Author",
            ),
            media=None,
            edit_date=None,
        )
        msg = ExportedMessage.from_telethon(obj)
        assert msg.forward_from_id == 444
        assert msg.forward_from_name == "Original Author"

    def test_photo_media(self) -> None:
        date = datetime(2026, 1, 15, 10, 33, tzinfo=UTC)

        class MessageMediaPhoto:
            photo = SimpleNamespace(sizes=[SimpleNamespace(size=84320)])
            document = None

        obj = SimpleNamespace(
            id=103,
            sender_id=111,
            sender=SimpleNamespace(first_name="Alice"),
            date=date,
            text=None,
            reply_to=None,
            forward=None,
            media=MessageMediaPhoto(),
            edit_date=None,
        )
        msg = ExportedMessage.from_telethon(obj)
        assert msg.media is not None
        assert msg.media.type == "photo"
        assert msg.media.size == 84320
        assert msg.media.file_name is None
        assert msg.text is None

    def test_photo_progressive_size(self) -> None:
        date = datetime(2026, 1, 15, 10, 33, tzinfo=UTC)

        class MessageMediaPhoto:
            photo = SimpleNamespace(sizes=[SimpleNamespace(size=None, sizes=[10000, 50000, 120000])])
            document = None

        obj = SimpleNamespace(
            id=109,
            sender_id=111,
            sender=SimpleNamespace(first_name="Alice"),
            date=date,
            text=None,
            reply_to=None,
            forward=None,
            media=MessageMediaPhoto(),
            edit_date=None,
        )
        msg = ExportedMessage.from_telethon(obj)
        assert msg.media is not None
        assert msg.media.size == 120000

    def test_document_media(self) -> None:
        date = datetime(2026, 1, 15, 10, 33, tzinfo=UTC)

        class MessageMediaDocument:
            photo = None
            document = SimpleNamespace(
                mime_type="application/pdf",
                size=125000,
                attributes=[SimpleNamespace(file_name="homework.pdf")],
            )

        obj = SimpleNamespace(
            id=108,
            sender_id=111,
            sender=SimpleNamespace(first_name="Alice"),
            date=date,
            text=None,
            reply_to=None,
            forward=None,
            media=MessageMediaDocument(),
            edit_date=None,
        )
        msg = ExportedMessage.from_telethon(obj)
        assert msg.media is not None
        assert msg.media.type == "document"
        assert msg.media.file_name == "homework.pdf"
        assert msg.media.mime_type == "application/pdf"
        assert msg.media.size == 125000

    def test_none_sender(self) -> None:
        date = datetime(2026, 1, 15, 10, 34, tzinfo=UTC)
        obj = SimpleNamespace(
            id=104,
            sender_id=None,
            sender=None,
            date=date,
            text="Channel post",
            reply_to=None,
            forward=None,
            media=None,
            edit_date=None,
        )
        msg = ExportedMessage.from_telethon(obj)
        assert msg.sender_id is None
        assert msg.sender_name is None

    def test_entities(self) -> None:
        date = datetime(2026, 1, 15, 10, 35, tzinfo=UTC)

        class MessageEntityBold:
            offset = 0
            length = 5

        class MessageEntityTextUrl:
            offset = 6
            length = 4
            url = "https://example.com"

        obj = SimpleNamespace(
            id=106,
            sender_id=111,
            sender=SimpleNamespace(first_name="Alice"),
            date=date,
            text="Hello link",
            reply_to=None,
            forward=None,
            media=None,
            entities=[MessageEntityBold(), MessageEntityTextUrl()],
            edit_date=None,
        )
        msg = ExportedMessage.from_telethon(obj)
        assert msg.entities is not None
        assert len(msg.entities) == 2
        assert msg.entities[0].type == "bold"
        assert msg.entities[0].offset == 0
        assert msg.entities[0].length == 5
        assert msg.entities[0].url is None
        assert msg.entities[1].type == "texturl"
        assert msg.entities[1].url == "https://example.com"

    def test_no_entities(self) -> None:
        date = datetime(2026, 1, 15, 10, 36, tzinfo=UTC)
        obj = SimpleNamespace(
            id=107,
            sender_id=111,
            sender=SimpleNamespace(first_name="Alice"),
            date=date,
            text="Plain text",
            reply_to=None,
            forward=None,
            media=None,
            entities=None,
            edit_date=None,
        )
        msg = ExportedMessage.from_telethon(obj)
        assert msg.entities is None

    def test_edited_message(self) -> None:
        date = datetime(2026, 1, 15, 10, 30, tzinfo=UTC)
        edit_date = datetime(2026, 1, 15, 11, 0, tzinfo=UTC)
        obj = SimpleNamespace(
            id=105,
            sender_id=111,
            sender=SimpleNamespace(first_name="Alice"),
            date=date,
            text="Edited text",
            reply_to=None,
            forward=None,
            media=None,
            edit_date=edit_date,
        )
        msg = ExportedMessage.from_telethon(obj)
        assert msg.edit_date == edit_date


class TestExportState:
    def test_roundtrip(self) -> None:
        now = datetime(2026, 3, 24, 16, 0, tzinfo=UTC)
        state = ExportState(newest_id=1042, oldest_id=1, last_sync_date=now, total_messages=1042)
        json_str = state.model_dump_json()
        restored = ExportState.model_validate_json(json_str)
        assert restored.newest_id == 1042
        assert restored.oldest_id == 1
        assert restored.total_messages == 1042
        assert restored.tracked is True

    def test_tracked_defaults_true(self) -> None:
        now = datetime(2026, 3, 24, 16, 0, tzinfo=UTC)
        state = ExportState.model_validate_json(
            '{"newest_id": 1, "oldest_id": 1, "last_sync_date": "' + now.isoformat() + '", "total_messages": 1}'
        )
        assert state.tracked is True


class TestCheckpoint:
    def test_roundtrip(self) -> None:
        now = datetime(2026, 3, 24, 16, 0, tzinfo=UTC)
        cp = Checkpoint(id=now, created_at=now, newest_id=500, prev_newest_id=400, delta_count=100)
        restored = Checkpoint.model_validate_json(cp.model_dump_json())
        assert restored.newest_id == 500
        assert restored.prev_newest_id == 400
        assert restored.delta_count == 100
