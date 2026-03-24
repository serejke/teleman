from __future__ import annotations

from collections.abc import Callable
from datetime import datetime

from teleman.client import TelemanClient
from teleman.export.models import ExportedMessage, ExportState
from teleman.export.resolver import resolve_chat
from teleman.export.storage import (
    append_messages,
    get_chat_dir,
    get_data_dir,
    read_state,
    write_meta,
    write_state,
)

BATCH_SIZE = 100


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

    batch: list[ExportedMessage] = []
    count = 0
    last_id = min_id

    async for msg in client.raw.iter_messages(entity, reverse=True, min_id=min_id):
        exported = ExportedMessage.from_telethon(msg)
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
