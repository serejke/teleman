from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING, Any

from teleman.export.models import ChatMeta

if TYPE_CHECKING:
    from teleman.client import TelemanClient


async def list_dialogs(client: TelemanClient) -> list[tuple[ChatMeta, Any]]:
    results: list[tuple[ChatMeta, Any]] = []
    now = datetime.now(tz=datetime.now().astimezone().tzinfo)
    async for dialog in client.raw.iter_dialogs():
        entity = dialog.entity
        meta = ChatMeta.from_telethon(entity, now=now)
        results.append((meta, entity))
    return results


async def resolve_chat(client: TelemanClient, query: str) -> tuple[ChatMeta, Any]:
    dialogs = await list_dialogs(client)
    query_lower = query.lower()

    # Try exact match first
    for meta, entity in dialogs:
        if meta.title.lower() == query_lower:
            return meta, entity

    # Try numeric chat ID
    try:
        chat_id = int(query)
        for meta, entity in dialogs:
            if meta.chat_id == chat_id:
                return meta, entity
    except ValueError:
        pass

    # Substring match
    matches = [(meta, entity) for meta, entity in dialogs if query_lower in meta.title.lower()]

    if len(matches) == 1:
        return matches[0]

    if len(matches) > 1:
        names = ", ".join(f'"{m.title}"' for m, _ in matches[:5])
        raise ValueError(f'Ambiguous query "{query}", matches: {names}')

    raise ValueError(f'No chat found matching "{query}"')
