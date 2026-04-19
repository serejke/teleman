from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import TYPE_CHECKING

from telethon.tl.functions.messages import GetForumTopicsRequest

from teleman.export.models import Checkpoint, ExportedMessage, ExportState, ForumTopic
from teleman.export.resolver import resolve_chat
from teleman.export.storage import (
    append_backfill,
    append_checkpoint,
    append_messages,
    finalize_backfill,
    get_chat_dir,
    get_data_dir,
    read_backfill_head,
    read_backfill_tail,
    read_state,
    write_meta,
    write_state,
    write_topics,
)

if TYPE_CHECKING:
    from collections.abc import Callable
    from pathlib import Path

    from teleman.client import TelemanClient

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
        topics.extend(ForumTopic.from_telethon(t) for t in result.topics)

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
) -> tuple[int, int | None, int | None, datetime | None]:
    """Fetch messages older than offset_id, newest→oldest, stop at `since` date.

    Streams batches to `messages.backfill.jsonl` as they arrive (iteration
    order = newest-first). On completion, stream-reverses the tmp file and
    prepends to messages.jsonl via atomic rename. If an earlier run was
    interrupted and left a tmp file, this run resumes from the oldest
    message already buffered there.
    Returns (finalized_count, new_oldest_id, seen_newest_id, seen_newest_date).
    """
    tail = read_backfill_tail(chat_dir)
    head = read_backfill_head(chat_dir) if tail is not None else None

    resume_offset_id = tail[0] if tail is not None else offset_id

    batch: list[ExportedMessage] = []
    this_run_appended = 0
    this_run_oldest_id: int | None = None
    seen_newest_id: int | None = head[0] if head is not None else None
    seen_newest_date: datetime | None = head[1] if head is not None else None

    async for msg in client.raw.iter_messages(entity, offset_id=resume_offset_id):
        if since is not None and msg.date < since:
            break
        if until is not None and msg.date > until:
            continue
        if seen_newest_id is None:
            seen_newest_id = msg.id
            seen_newest_date = msg.date
        exported = ExportedMessage.from_telethon(msg, topic_root_ids=topic_root_ids)
        batch.append(exported)
        this_run_oldest_id = msg.id
        this_run_appended += 1

        if len(batch) >= BATCH_SIZE:
            append_backfill(chat_dir, batch)
            batch = []
            if on_progress:
                on_progress(new_count, this_run_appended)

    if batch:
        append_backfill(chat_dir, batch)
        if on_progress:
            on_progress(new_count, this_run_appended)

    if tail is None and this_run_appended == 0:
        return 0, None, None, None

    finalized = finalize_backfill(chat_dir)
    new_oldest_id = (
        this_run_oldest_id if this_run_oldest_id is not None else (tail[0] if tail else None)
    )
    return finalized, new_oldest_id, seen_newest_id, seen_newest_date


async def sync_chat(
    client: TelemanClient,
    query: str,
    *,
    since: datetime | None = None,
    until: datetime | None = None,
    all_history: bool = False,
    forward_only: bool = False,
    on_progress: Callable[[int, int], None] | None = None,
) -> SyncResult:
    """Sync a chat: always forward catch-up + backward fill (unless forward_only).

    - First-ever sync with neither `since` nor `all_history` returns
      `bootstrap_required=True` as a safety guard against accidentally
      fetching an entire chat's history.
    - `forward_only=True` skips the backward pass (used by `sync --all`
      batch mode on existing-state chats).
    - A checkpoint is written whenever `newest_id` advances, which covers
      both forward deltas and first-time bootstraps.
    """
    meta, entity = await resolve_chat(client, query)

    data_dir = get_data_dir()
    chat_dir = get_chat_dir(data_dir, meta.chat_id)

    state = read_state(chat_dir)
    resumed = state is not None

    if state is None and since is None and not all_history:
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
    seen_newest_date_from_backfill: datetime | None = None
    run_backfill = not forward_only
    if run_backfill:
        backfill_offset = state.oldest_id if state is not None else 0
        (
            backfill_count,
            new_oldest_id,
            seen_newest_from_backfill,
            seen_newest_date_from_backfill,
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
        new_newest_id
        if new_newest_id is not None
        else (state.newest_id if state else seen_newest_from_backfill)
    )
    oldest_id = (
        new_oldest_id
        if new_oldest_id is not None
        else (state.oldest_id if state else seen_newest_from_backfill)
    )

    effective_tracked = state.tracked if state is not None else True

    # Checkpoint rule: whenever newest_id advances.
    checkpoint: Checkpoint | None = None
    prev_newest = state.newest_id if state else 0
    cp_newest_date = (
        new_newest_date if new_newest_date is not None else seen_newest_date_from_backfill
    )
    if newest_id is not None and newest_id > prev_newest and cp_newest_date is not None:
        delta = newest_id - prev_newest if state else (new_count + backfill_count)
        checkpoint = Checkpoint(
            id=cp_newest_date,
            created_at=now,
            newest_id=newest_id,
            prev_newest_id=prev_newest,
            delta_count=delta,
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
