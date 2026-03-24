from __future__ import annotations

from telethon.tl.functions.contacts import AddContactRequest

from teleman.client import TelemanClient
from teleman.models import Group, Peer, User


async def get_user(client: TelemanClient, user_id: int | str) -> User:
    entity = await client.raw.get_entity(user_id)
    return User.from_telethon(entity)


async def get_peer(client: TelemanClient, peer_id: int | str) -> Peer:
    entity = await client.raw.get_entity(peer_id)
    if hasattr(entity, "first_name"):
        return User.from_telethon(entity)
    return Group.from_telethon(entity)


def peer_name(peer: Peer) -> str:
    if isinstance(peer, User):
        return peer.first_name
    return peer.title


async def add_contact(client: TelemanClient, user_id: int | str) -> User:
    entity = await client.raw.get_entity(user_id)
    await client.raw(
        AddContactRequest(
            id=entity,
            first_name=entity.first_name or "",
            last_name=entity.last_name or "",
            phone="",
        )
    )
    return User.from_telethon(entity)
