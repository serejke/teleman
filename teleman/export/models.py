from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel


class ChatMeta(BaseModel):
    chat_id: int
    title: str
    type: str  # "user", "group", "channel"
    username: str | None = None
    megagroup: bool = False
    forum: bool = False
    participants_count: int | None = None
    exported_at: datetime
    updated_at: datetime

    @classmethod
    def from_telethon(cls, obj: Any, *, now: datetime | None = None) -> ChatMeta:
        ts = now or datetime.now(tz=datetime.now().astimezone().tzinfo)

        if hasattr(obj, "first_name"):
            return cls(
                chat_id=obj.id,
                title=obj.first_name or "",
                type="user",
                username=getattr(obj, "username", None),
                exported_at=ts,
                updated_at=ts,
            )

        chat_type = "channel" if getattr(obj, "broadcast", False) else "group"
        return cls(
            chat_id=obj.id,
            title=obj.title or "",
            type=chat_type,
            username=getattr(obj, "username", None),
            megagroup=getattr(obj, "megagroup", False) or False,
            forum=getattr(obj, "forum", False) or False,
            participants_count=getattr(obj, "participants_count", None),
            exported_at=ts,
            updated_at=ts,
        )


def _extract_sender_name(sender: Any) -> str | None:
    if sender is None:
        return None
    if hasattr(sender, "first_name"):
        parts = [sender.first_name or "", getattr(sender, "last_name", None) or ""]
        return " ".join(p for p in parts if p) or None
    if hasattr(sender, "title"):
        title = sender.title
        return str(title) if title else None
    return None


def _extract_forward_from(fwd: Any) -> tuple[int | None, str | None]:
    if fwd is None:
        return None, None
    from_id = getattr(fwd, "from_id", None)
    from_name = getattr(fwd, "from_name", None)
    if from_id is not None:
        sender_id = getattr(from_id, "user_id", None) or getattr(from_id, "channel_id", None)
        return sender_id, from_name
    return None, from_name


class MessageEntity(BaseModel):
    type: str
    offset: int
    length: int
    url: str | None = None


def _extract_entities(entities: Any) -> list[MessageEntity] | None:
    if not entities:
        return None
    result: list[MessageEntity] = []
    for e in entities:
        name = type(e).__name__
        prefix = "MessageEntity"
        entity_type = name[len(prefix) :].lower() if name.startswith(prefix) else name.lower()
        result.append(
            MessageEntity(
                type=entity_type,
                offset=e.offset,
                length=e.length,
                url=getattr(e, "url", None),
            )
        )
    return result or None


class MediaInfo(BaseModel):
    type: str  # "photo", "document", "video", "audio", "sticker", "voice", etc.
    file_name: str | None = None
    mime_type: str | None = None
    size: int | None = None


def _extract_media(media: Any) -> MediaInfo | None:
    if media is None:
        return None

    name = type(media).__name__
    prefix = "MessageMedia"
    media_type = name[len(prefix) :].lower() if name.startswith(prefix) else name.lower()

    file_name: str | None = None
    mime_type: str | None = None
    size: int | None = None

    # Photos: size is in the largest photo size
    photo = getattr(media, "photo", None)
    if photo is not None and not isinstance(photo, bool):
        sizes = getattr(photo, "sizes", None)
        if sizes:
            last = sizes[-1]
            # PhotoSize has .size, PhotoSizeProgressive has .sizes (list of ints)
            size = getattr(last, "size", None)
            if size is None:
                progressive_sizes = getattr(last, "sizes", None)
                if progressive_sizes:
                    size = max(progressive_sizes)

    # Documents (files, video, audio, stickers, voice, etc.)
    doc = getattr(media, "document", None)
    if doc is not None:
        mime_type = getattr(doc, "mime_type", None)
        size = getattr(doc, "size", None)
        for attr in getattr(doc, "attributes", []):
            fn = getattr(attr, "file_name", None)
            if fn:
                file_name = fn
                break

    return MediaInfo(
        type=media_type,
        file_name=file_name,
        mime_type=mime_type,
        size=size,
    )


class ExportedMessage(BaseModel):
    id: int
    sender_id: int | None = None
    sender_name: str | None = None
    sender_username: str | None = None
    date: datetime
    text: str | None = None
    reply_to_msg_id: int | None = None
    topic_id: int | None = None
    forward_from_id: int | None = None
    forward_from_name: str | None = None
    media: MediaInfo | None = None
    entities: list[MessageEntity] | None = None
    edit_date: datetime | None = None

    @classmethod
    def from_telethon(
        cls,
        obj: Any,
        *,
        topic_root_ids: set[int] | None = None,
    ) -> ExportedMessage:
        reply_to = getattr(obj, "reply_to", None)
        reply_to_msg_id = getattr(reply_to, "reply_to_msg_id", None) if reply_to else None
        topic_id: int | None = None
        if reply_to is not None and getattr(reply_to, "forum_topic", False):
            top_id = getattr(reply_to, "reply_to_top_id", None)
            # First message in a topic: reply_to_msg_id IS the topic id
            topic_id = top_id if top_id is not None else reply_to_msg_id
        elif topic_root_ids is not None:
            # A message creates its own topic when its id is a root id; otherwise General (1)
            topic_id = obj.id if obj.id in topic_root_ids else 1

        fwd_from_id, fwd_from_name = _extract_forward_from(getattr(obj, "forward", None))

        return cls(
            id=obj.id,
            sender_id=getattr(obj, "sender_id", None),
            sender_name=_extract_sender_name(getattr(obj, "sender", None)),
            sender_username=getattr(getattr(obj, "sender", None), "username", None),
            date=obj.date,
            text=getattr(obj, "text", None),
            reply_to_msg_id=reply_to_msg_id,
            topic_id=topic_id,
            forward_from_id=fwd_from_id,
            forward_from_name=fwd_from_name,
            media=_extract_media(getattr(obj, "media", None)),
            entities=_extract_entities(getattr(obj, "entities", None)),
            edit_date=getattr(obj, "edit_date", None),
        )


class ForumTopic(BaseModel):
    id: int
    title: str
    icon_emoji_id: int | None = None
    closed: bool = False

    @classmethod
    def from_telethon(cls, obj: Any) -> ForumTopic:
        return cls(
            id=obj.id,
            title=obj.title,
            icon_emoji_id=getattr(obj, "icon_emoji_id", None),
            closed=getattr(obj, "closed", False) or False,
        )


class ExportState(BaseModel):
    newest_id: int
    oldest_id: int
    last_sync_date: datetime
    total_messages: int
    tracked: bool = True


class Checkpoint(BaseModel):
    id: datetime  # ISO timestamp of the newest message in the delta
    created_at: datetime  # wall-clock time of the sync run
    newest_id: int
    prev_newest_id: int
    delta_count: int
