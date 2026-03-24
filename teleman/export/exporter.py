from __future__ import annotations

from collections.abc import Callable
from datetime import datetime

from teleman.client import TelemanClient
from teleman.export.models import ExportedMessage, ExportState, ForumTopic
from teleman.export.resolver import resolve_chat
from teleman.export.storage import (
    append_messages,
    get_chat_dir,
    get_data_dir,
    read_state,
    write_meta,
    write_state,
    write_topics,
)

BATCH_SIZE = 100


async def _fetch_forum_topics(
    client: TelemanClient,
    entity: object,
) -> list[ForumTopic]:
    from telethon.tl.functions.messages import GetForumTopicsRequest

    topics: list[ForumTopic] = []
    offset_date: datetime | None = None
    offset_id = 0
    offset_topic = 0

    while True:
        result = await client.raw(
            GetForumTopicsRequest(
                peer=entity,
                offset_date=offset_date,
                offset_id=offset_id,
                offset_topic=offset_topic,
                limit=100,
            )
        )
        for t in result.topics:
            topics.append(ForumTopic.from_telethon(t))

        if not result.topics or len(topics) >= result.count:
            break

        last = result.topics[-1]
        offset_date = last.date
        offset_id = last.top_message
        offset_topic = last.id

    return topics


async def export_chat(
    client: TelemanClient,
    query: str,
    on_progress: Callable[[int], None] | None = None,
) -> tuple[str, int, bool]:
    """Export a chat's messages to JSONL.

    Returns (chat_title, new_message_count, is_incremental).
    """
    meta, entity = await resolve_chat(client, query)

    data_dir = get_data_dir()
    chat_dir = get_chat_dir(data_dir, meta.chat_id)

    state = read_state(chat_dir)
    is_incremental = state is not None
    min_id = state.last_message_id if state else 0
    prior_total = state.total_messages if state else 0

    # Fetch forum topics before iterating messages so we can tag each message
    topics: list[ForumTopic] = []
    topic_root_ids: set[int] | None = None
    if meta.forum:
        topics = await _fetch_forum_topics(client, entity)
        topic_root_ids = {t.id for t in topics}

    batch: list[ExportedMessage] = []
    count = 0
    last_id = min_id

    async for msg in client.raw.iter_messages(entity, reverse=True, min_id=min_id):
        exported = ExportedMessage.from_telethon(msg, topic_root_ids=topic_root_ids)
        batch.append(exported)
        last_id = max(last_id, msg.id)
        count += 1

        if len(batch) >= BATCH_SIZE:
            append_messages(chat_dir, batch)
            batch.clear()
            if on_progress:
                on_progress(count)

    if batch:
        append_messages(chat_dir, batch)
        if on_progress:
            on_progress(count)

    now = datetime.now(tz=datetime.now().astimezone().tzinfo)
    meta.updated_at = now
    write_meta(chat_dir, meta)

    if topics:
        write_topics(chat_dir, topics)

    if count > 0 or state is None:
        write_state(
            chat_dir,
            ExportState(
                last_message_id=last_id,
                last_export_date=now,
                total_messages=prior_total + count,
            ),
        )

    return meta.title, count, is_incremental
