from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from teleman.client import TelemanClient
from teleman.export.models import Checkpoint, ExportedMessage, ExportState, ForumTopic
from teleman.export.resolver import resolve_chat
from teleman.export.storage import (
    append_checkpoint,
    append_messages,
    get_chat_dir,
    get_data_dir,
    prepend_messages,
    read_state,
    write_meta,
    write_state,
    write_topics,
)

BATCH_SIZE = 100


@dataclass
class SyncResult:
    title: str
    new_count: int
    backfilled_count: int
    total_messages: int
    resumed: bool
    checkpoint: Checkpoint | None
    bootstrap_required: bool = False


async def _fetch_forum_topics(client: TelemanClient, entity: object) -> list[ForumTopic]:
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


async def _catch_up_newer(
    client: TelemanClient,
    entity: object,
    chat_dir: Path,
    since_newest_id: int,
    topic_root_ids: set[int] | None,
    on_progress: Callable[[int, int], None] | None,
) -> tuple[int, int | None, datetime | None]:
    """Fetch messages with id > since_newest_id, newest→oldest.

    Streams batches in reverse (oldest→newest) to the end of messages.jsonl.
    Returns (count, new_newest_id, new_newest_date).
    """
    batch: list[ExportedMessage] = []
    count = 0
    new_newest_id: int | None = None
    new_newest_date: datetime | None = None

    async for msg in client.raw.iter_messages(entity, min_id=since_newest_id):
        if new_newest_id is None:
            new_newest_id = msg.id
            new_newest_date = msg.date
        exported = ExportedMessage.from_telethon(msg, topic_root_ids=topic_root_ids)
        batch.append(exported)
        count += 1

        if len(batch) >= BATCH_SIZE:
            batch.reverse()
            append_messages(chat_dir, batch)
            batch = []
            if on_progress:
                on_progress(count, 0)

    if batch:
        batch.reverse()
        append_messages(chat_dir, batch)
        if on_progress:
            on_progress(count, 0)

    return count, new_newest_id, new_newest_date


async def _backfill_older(
    client: TelemanClient,
    entity: object,
    chat_dir: Path,
    offset_id: int,
    since: datetime | None,
    until: datetime | None,
    topic_root_ids: set[int] | None,
    on_progress: Callable[[int, int], None] | None,
    new_count: int,
) -> tuple[int, int | None, int | None]:
    """Fetch messages older than offset_id, newest→oldest, stop at `since` date.

    Buffers the whole backfill in memory, then prepends chronologically.
    Returns (count, new_oldest_id, seen_newest_id).
    """
    buffer: list[ExportedMessage] = []
    new_oldest_id: int | None = None
    seen_newest_id: int | None = None

    async for msg in client.raw.iter_messages(entity, offset_id=offset_id):
        if since is not None and msg.date < since:
            break
        if until is not None and msg.date > until:
            continue
        if seen_newest_id is None:
            seen_newest_id = msg.id
        exported = ExportedMessage.from_telethon(msg, topic_root_ids=topic_root_ids)
        buffer.append(exported)
        new_oldest_id = msg.id

        if on_progress and len(buffer) % BATCH_SIZE == 0:
            on_progress(new_count, len(buffer))

    if not buffer:
        return 0, None, None

    buffer.reverse()
    prepend_messages(chat_dir, buffer)
    if on_progress:
        on_progress(new_count, len(buffer))
    return len(buffer), new_oldest_id, seen_newest_id


async def sync_chat(
    client: TelemanClient,
    query: str,
    *,
    backfill: bool = False,
    since: datetime | None = None,
    until: datetime | None = None,
    track: bool = True,
    on_progress: Callable[[int, int], None] | None = None,
) -> SyncResult:
    """Sync a chat: forward catch-up + optional backward backfill.

    - Forward catch-up runs whenever state exists; writes a checkpoint if delta > 0.
    - Backfill runs only when `backfill=True`; never writes a checkpoint.
    - First sync (no state) with backfill=False returns bootstrap_required=True (no-op).
    """
    meta, entity = await resolve_chat(client, query)

    data_dir = get_data_dir()
    chat_dir = get_chat_dir(data_dir, meta.chat_id)

    state = read_state(chat_dir)
    resumed = state is not None

    if state is None and not backfill:
        return SyncResult(
            title=meta.title,
            new_count=0,
            backfilled_count=0,
            total_messages=0,
            resumed=False,
            checkpoint=None,
            bootstrap_required=True,
        )

    topics: list[ForumTopic] = []
    topic_root_ids: set[int] | None = None
    if meta.forum:
        topics = await _fetch_forum_topics(client, entity)
        topic_root_ids = {t.id for t in topics}

    new_count = 0
    new_newest_id: int | None = None
    new_newest_date: datetime | None = None
    if state is not None:
        new_count, new_newest_id, new_newest_date = await _catch_up_newer(
            client,
            entity,
            chat_dir,
            since_newest_id=state.newest_id,
            topic_root_ids=topic_root_ids,
            on_progress=on_progress,
        )

    backfill_count = 0
    new_oldest_id: int | None = None
    seen_newest_from_backfill: int | None = None
    if backfill:
        backfill_offset = state.oldest_id if state is not None else 0
        (
            backfill_count,
            new_oldest_id,
            seen_newest_from_backfill,
        ) = await _backfill_older(
            client,
            entity,
            chat_dir,
            offset_id=backfill_offset,
            since=since,
            until=until,
            topic_root_ids=topic_root_ids,
            on_progress=on_progress,
            new_count=new_count,
        )

    now = datetime.now(tz=datetime.now().astimezone().tzinfo)
    meta.updated_at = now
    write_meta(chat_dir, meta)

    if topics:
        write_topics(chat_dir, topics)

    prior_total = state.total_messages if state else 0
    total_messages = prior_total + new_count + backfill_count

    newest_id = (
        new_newest_id if new_newest_id is not None else (state.newest_id if state else seen_newest_from_backfill)
    )
    oldest_id = (
        new_oldest_id if new_oldest_id is not None else (state.oldest_id if state else seen_newest_from_backfill)
    )

    effective_tracked = state.tracked if state is not None else track

    checkpoint: Checkpoint | None = None
    if new_count > 0 and new_newest_id is not None and new_newest_date is not None:
        prev_newest = state.newest_id if state else 0
        checkpoint = Checkpoint(
            id=new_newest_date,
            created_at=now,
            newest_id=new_newest_id,
            prev_newest_id=prev_newest,
            delta_count=new_count,
        )
        append_checkpoint(chat_dir, checkpoint)

    if newest_id is not None and oldest_id is not None:
        write_state(
            chat_dir,
            ExportState(
                newest_id=newest_id,
                oldest_id=oldest_id,
                last_sync_date=now,
                total_messages=total_messages,
                tracked=effective_tracked,
            ),
        )

    return SyncResult(
        title=meta.title,
        new_count=new_count,
        backfilled_count=backfill_count,
        total_messages=total_messages,
        resumed=resumed,
        checkpoint=checkpoint,
    )
