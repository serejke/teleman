from __future__ import annotations

from typing import Any

from teleman.client import TelemanClient
from teleman.models import Message


async def get_messages(client: TelemanClient, user_id: int | str, limit: int = 20) -> list[Message]:
    raw_messages = await get_raw_messages(client, user_id, limit=limit)
    return [Message.from_telethon(m) for m in raw_messages]


async def get_raw_messages(client: TelemanClient, user_id: int | str, limit: int = 20) -> list[Any]:
    return list(await client.raw.get_messages(user_id, limit=limit))


async def send_message(client: TelemanClient, user_id: int | str, text: str) -> Message:
    raw_message = await client.raw.send_message(user_id, text)
    return Message.from_telethon(raw_message)


async def delete_all_messages(client: TelemanClient, user_id: int | str) -> int:
    """Delete all messages in a chat for both sides. Returns count of deleted messages."""
    messages = await client.raw.get_messages(user_id, limit=None)
    if not messages:
        return 0
    ids = [m.id for m in messages]
    deleted = 0
    for i in range(0, len(ids), 100):
        batch = ids[i : i + 100]
        await client.raw.delete_messages(user_id, batch, revoke=True)
        deleted += len(batch)
    return deleted


async def delete_dialog(client: TelemanClient, user_id: int | str) -> None:
    """Remove a dialog/chat from the chat list."""
    await client.raw.delete_dialog(user_id)
