from __future__ import annotations

from teleman.client import TelemanClient
from teleman.contacts import add_contact, get_peer, peer_name
from teleman.export.exporter import export_chat as _export_chat
from teleman.export.resolver import list_dialogs
from teleman.messages import get_messages, send_message
from teleman.models import User
from teleman.responses import (
    AddContactResponse,
    ChatInfo,
    ChatsResponse,
    ContactsResponse,
    ExportListItem,
    ExportListResponse,
    ExportResponse,
    LockdownResponse,
    MessagesResponse,
    PrivacyResponse,
    SendResponse,
    SessionEndResponse,
    SessionsResponse,
    SettingsOverview,
    WebEndAllResponse,
    WebEndResponse,
    WebSessionsResponse,
)


async def cmd_me(client: TelemanClient) -> User:
    raw_me = await client.raw.get_me()
    return User.from_telethon(raw_me)


async def cmd_chats(client: TelemanClient) -> ChatsResponse:
    dialogs = await client.raw.get_dialogs()
    chats: list[ChatInfo] = []
    for d in dialogs:
        entity = d.entity
        username = getattr(entity, "username", None)
        if hasattr(entity, "first_name"):
            kind = "user"
        elif hasattr(entity, "title"):
            is_group = getattr(entity, "megagroup", False) or not getattr(entity, "broadcast", False)
            kind = "group" if is_group else "channel"
        else:
            kind = "unknown"
        chats.append(
            ChatInfo(
                id=entity.id,
                type=kind,
                username=username,
                unread_count=d.unread_count or 0,
            )
        )
    return ChatsResponse(chats=chats)


async def cmd_contacts(client: TelemanClient) -> ContactsResponse:
    from telethon.tl.functions.contacts import GetContactsRequest

    result = await client.raw(GetContactsRequest(hash=0))
    contacts = [User.from_telethon(u) for u in result.users]
    return ContactsResponse(contacts=contacts)


async def cmd_messages(client: TelemanClient, peer_id: int | str, limit: int = 20) -> MessagesResponse:
    messages = await get_messages(client, peer_id, limit=limit)
    return MessagesResponse(peer_id=peer_id, messages=messages)


async def cmd_send(client: TelemanClient, peer_id: int | str, text: str) -> SendResponse:
    msg = await send_message(client, peer_id, text)
    return SendResponse(message=msg)


async def cmd_add(client: TelemanClient, user_id: int | str) -> AddContactResponse:
    user = await add_contact(client, user_id)
    return AddContactResponse(user=user)


async def cmd_privacy(client: TelemanClient) -> PrivacyResponse:
    from teleman.privacy import get_privacy

    rules = await get_privacy(client)
    return PrivacyResponse(rules=rules)


async def cmd_privacy_set(client: TelemanClient, key: str, level: str) -> PrivacyResponse:
    from teleman.privacy import set_privacy

    rule = await set_privacy(client, key, level)
    return PrivacyResponse(rules=[rule])


async def cmd_lockdown(client: TelemanClient) -> LockdownResponse:
    from teleman.privacy import lockdown_privacy

    rules = await lockdown_privacy(client)
    return LockdownResponse(rules=rules)


async def cmd_sessions(client: TelemanClient) -> SessionsResponse:
    from teleman.sessions import get_sessions

    sessions = await get_sessions(client)
    return SessionsResponse(sessions=sessions)


async def cmd_session_end(client: TelemanClient, session_hash: int) -> SessionEndResponse:
    from teleman.sessions import end_session, get_sessions

    sessions = await get_sessions(client)
    target = next((s for s in sessions if s.hash == session_hash), None)
    if target is None:
        raise ValueError(f"No session found with hash {session_hash}")
    if target.current:
        raise ValueError("Cannot terminate the current session")
    await end_session(client, session_hash)
    return SessionEndResponse(hash=session_hash, device_model=target.device_model)


async def cmd_settings(client: TelemanClient) -> SettingsOverview:
    from teleman.privacy import get_privacy
    from teleman.sessions import get_sessions
    from teleman.settings import get_2fa_status, get_account_ttl, get_web_sessions

    tfa = await get_2fa_status(client)
    ttl = await get_account_ttl(client)
    privacy_rules = await get_privacy(client)
    sessions = await get_sessions(client)
    web_sessions = await get_web_sessions(client)
    return SettingsOverview(
        two_factor=tfa,
        account_ttl=ttl,
        privacy=privacy_rules,
        sessions=sessions,
        web_sessions=web_sessions,
    )


async def cmd_web_sessions(client: TelemanClient) -> WebSessionsResponse:
    from teleman.settings import get_web_sessions

    sessions = await get_web_sessions(client)
    return WebSessionsResponse(sessions=sessions)


async def cmd_web_end(client: TelemanClient, session_hash: int) -> WebEndResponse:
    from teleman.settings import end_web_session, get_web_sessions

    sessions = await get_web_sessions(client)
    target = next((s for s in sessions if s.hash == session_hash), None)
    if target is None:
        raise ValueError(f"No web session found with hash {session_hash}")
    await end_web_session(client, session_hash)
    return WebEndResponse(hash=session_hash, domain=target.domain)


async def cmd_web_end_all(client: TelemanClient) -> WebEndAllResponse:
    from teleman.settings import end_all_web_sessions

    await end_all_web_sessions(client)
    return WebEndAllResponse()


async def cmd_settings_2fa(client: TelemanClient) -> None:
    from teleman.settings import get_2fa_status

    return await get_2fa_status(client)


async def cmd_settings_ttl(client: TelemanClient) -> None:
    from teleman.settings import get_account_ttl

    return await get_account_ttl(client)


async def cmd_settings_ttl_set(client: TelemanClient, days: int) -> None:
    from teleman.settings import set_account_ttl

    return await set_account_ttl(client, days)


async def cmd_export_list(client: TelemanClient) -> ExportListResponse:
    dialogs = await list_dialogs(client)
    items = [
        ExportListItem(
            chat_id=meta.chat_id,
            title=meta.title,
            type=meta.type,
            username=meta.username,
        )
        for meta, _entity in dialogs
    ]
    return ExportListResponse(chats=items)


async def cmd_export(client: TelemanClient, query: str) -> ExportResponse:
    title, count, incremental = await _export_chat(client, query)
    return ExportResponse(title=title, message_count=count, incremental=incremental)


async def cmd_report(client: TelemanClient, user_id: int | str, reason_key: str, message: str = "") -> None:
    from teleman.report import report_peer

    return await report_peer(client, user_id, reason_key, message)


async def cmd_nuke(client: TelemanClient, peer_id: int | str) -> dict[str, object]:
    from teleman.messages import delete_all_messages, delete_dialog

    peer = await get_peer(client, peer_id)
    display = peer_name(peer)
    count = await delete_all_messages(client, peer_id)
    await delete_dialog(client, peer_id)
    return {"peer": display, "peer_id": peer.id, "deleted_messages": count}
