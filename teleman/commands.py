from __future__ import annotations

from typing import TYPE_CHECKING

from analysis.loader import load_messages
from analysis.loader import resolve_chat as resolve_chat_path
from telethon.tl.functions.contacts import GetContactsRequest

from teleman.contacts import add_contact, get_peer, peer_name
from teleman.export.resolver import list_dialogs, resolve_chat
from teleman.export.storage import (
    get_chat_dir,
    get_data_dir,
    list_tracked_chat_dirs,
    read_checkpoints,
    read_meta,
    read_state,
    write_state,
)
from teleman.export.sync import sync_chat as _sync_chat
from teleman.links import extract_links
from teleman.messages import (
    delete_all_messages,
    delete_dialog,
    get_messages,
    send_message,
)
from teleman.models import User
from teleman.privacy import get_privacy, lockdown_privacy, set_privacy
from teleman.report import report_peer
from teleman.responses import (
    AddContactResponse,
    BatchSyncError,
    BatchSyncItem,
    BatchSyncResponse,
    ChatInfo,
    ChatsResponse,
    CheckpointsResponse,
    ContactsResponse,
    ExportListItem,
    ExportListResponse,
    LinkItem,
    LinksResponse,
    LockdownResponse,
    MessagesResponse,
    PrivacyResponse,
    SendResponse,
    SessionEndResponse,
    SessionsResponse,
    SettingsOverview,
    SyncResponse,
    TrackedChat,
    TrackedResponse,
    TrackResponse,
    WebEndAllResponse,
    WebEndResponse,
    WebSessionsResponse,
)
from teleman.sessions import end_session, get_sessions
from teleman.settings import (
    end_all_web_sessions,
    end_web_session,
    get_2fa_status,
    get_account_ttl,
    get_web_sessions,
    set_account_ttl,
)

if TYPE_CHECKING:
    from datetime import datetime

    from teleman.client import TelemanClient


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
            is_group = getattr(entity, "megagroup", False) or not getattr(
                entity, "broadcast", False
            )
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
    result = await client.raw(GetContactsRequest(hash=0))
    contacts = [User.from_telethon(u) for u in result.users]
    return ContactsResponse(contacts=contacts)


async def cmd_messages(
    client: TelemanClient, peer_id: int | str, limit: int = 20
) -> MessagesResponse:
    messages = await get_messages(client, peer_id, limit=limit)
    return MessagesResponse(peer_id=peer_id, messages=messages)


async def cmd_send(client: TelemanClient, peer_id: int | str, text: str) -> SendResponse:
    msg = await send_message(client, peer_id, text)
    return SendResponse(message=msg)


async def cmd_add(client: TelemanClient, user_id: int | str) -> AddContactResponse:
    user = await add_contact(client, user_id)
    return AddContactResponse(user=user)


async def cmd_privacy(client: TelemanClient) -> PrivacyResponse:
    rules = await get_privacy(client)
    return PrivacyResponse(rules=rules)


async def cmd_privacy_set(client: TelemanClient, key: str, level: str) -> PrivacyResponse:
    rule = await set_privacy(client, key, level)
    return PrivacyResponse(rules=[rule])


async def cmd_lockdown(client: TelemanClient) -> LockdownResponse:
    rules = await lockdown_privacy(client)
    return LockdownResponse(rules=rules)


async def cmd_sessions(client: TelemanClient) -> SessionsResponse:
    sessions = await get_sessions(client)
    return SessionsResponse(sessions=sessions)


async def cmd_session_end(client: TelemanClient, session_hash: int) -> SessionEndResponse:
    sessions = await get_sessions(client)
    target = next((s for s in sessions if s.hash == session_hash), None)
    if target is None:
        raise ValueError(f"No session found with hash {session_hash}")
    if target.current:
        raise ValueError("Cannot terminate the current session")
    await end_session(client, session_hash)
    return SessionEndResponse(hash=session_hash, device_model=target.device_model)


async def cmd_settings(client: TelemanClient) -> SettingsOverview:
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
    sessions = await get_web_sessions(client)
    return WebSessionsResponse(sessions=sessions)


async def cmd_web_end(client: TelemanClient, session_hash: int) -> WebEndResponse:
    sessions = await get_web_sessions(client)
    target = next((s for s in sessions if s.hash == session_hash), None)
    if target is None:
        raise ValueError(f"No web session found with hash {session_hash}")
    await end_web_session(client, session_hash)
    return WebEndResponse(hash=session_hash, domain=target.domain)


async def cmd_web_end_all(client: TelemanClient) -> WebEndAllResponse:
    await end_all_web_sessions(client)
    return WebEndAllResponse()


async def cmd_settings_2fa(client: TelemanClient) -> None:
    return await get_2fa_status(client)


async def cmd_settings_ttl(client: TelemanClient) -> None:
    return await get_account_ttl(client)


async def cmd_settings_ttl_set(client: TelemanClient, days: int) -> None:
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


async def cmd_sync(
    client: TelemanClient,
    query: str,
    *,
    since: datetime | None = None,
    until: datetime | None = None,
    all_history: bool = False,
) -> SyncResponse:
    result = await _sync_chat(
        client,
        query,
        since=since,
        until=until,
        all_history=all_history,
    )
    return SyncResponse(
        title=result.title,
        new_count=result.new_count,
        backfilled_count=result.backfilled_count,
        total_messages=result.total_messages,
        resumed=result.resumed,
        checkpoint=result.checkpoint,
        bootstrap_required=result.bootstrap_required,
    )


async def cmd_sync_all(client: TelemanClient) -> BatchSyncResponse:
    data_dir = get_data_dir()
    tracked_dirs = list_tracked_chat_dirs(data_dir)

    results: list[BatchSyncItem] = []
    errors: list[BatchSyncError] = []

    for chat_dir in tracked_dirs:
        chat_id = int(chat_dir.name)
        meta = read_meta(chat_dir)
        title = meta.title if meta else chat_dir.name
        try:
            result = await _sync_chat(client, str(chat_id), forward_only=True)
            results.append(
                BatchSyncItem(
                    chat_id=chat_id,
                    title=result.title,
                    new_count=result.new_count,
                    backfilled_count=result.backfilled_count,
                    total_messages=result.total_messages,
                    resumed=result.resumed,
                    checkpoint=result.checkpoint,
                )
            )
        except Exception as exc:
            errors.append(BatchSyncError(chat_id=chat_id, title=title, error=str(exc)))

    return BatchSyncResponse(results=results, errors=errors)


async def _set_tracked(client: TelemanClient, query: str, tracked: bool) -> TrackResponse:
    meta, _entity = await resolve_chat(client, query)
    chat_dir = get_chat_dir(get_data_dir(), meta.chat_id)
    state = read_state(chat_dir)
    if state is None:
        raise ValueError(
            f'No export state for "{meta.title}". Run `sync <chat> --since <date>` to bootstrap.'
        )
    state.tracked = tracked
    write_state(chat_dir, state)
    return TrackResponse(chat_id=meta.chat_id, title=meta.title, tracked=tracked)


async def cmd_track(client: TelemanClient, query: str) -> TrackResponse:
    return await _set_tracked(client, query, tracked=True)


async def cmd_untrack(client: TelemanClient, query: str) -> TrackResponse:
    return await _set_tracked(client, query, tracked=False)


def cmd_tracked() -> TrackedResponse:
    data_dir = get_data_dir()
    tracked_dirs = list_tracked_chat_dirs(data_dir)
    chats: list[TrackedChat] = []
    for chat_dir in tracked_dirs:
        meta = read_meta(chat_dir)
        state = read_state(chat_dir)
        if meta is None or state is None:
            continue
        chats.append(
            TrackedChat(
                chat_id=meta.chat_id,
                title=meta.title,
                type=meta.type,
                username=meta.username,
                newest_id=state.newest_id,
                last_sync_date=state.last_sync_date,
            )
        )
    return TrackedResponse(chats=chats)


async def cmd_checkpoints(client: TelemanClient, query: str) -> CheckpointsResponse:
    meta, _entity = await resolve_chat(client, query)
    chat_dir = get_chat_dir(get_data_dir(), meta.chat_id)
    checkpoints = read_checkpoints(chat_dir)
    return CheckpointsResponse(chat_id=meta.chat_id, title=meta.title, checkpoints=checkpoints)


def cmd_links(
    query: str,
    *,
    after: datetime | None = None,
    before: datetime | None = None,
) -> LinksResponse:
    path = resolve_chat_path(query)
    messages = load_messages(path)
    extracted = extract_links(messages, after=after, before=before)
    items = [
        LinkItem(
            url=link.url,
            message_id=link.message_id,
            date=link.date,
            sender_id=link.sender_id,
            sender_name=link.sender_name,
        )
        for link in extracted
    ]
    return LinksResponse(query=query, links=items, total=len(items))


async def cmd_report(
    client: TelemanClient, user_id: int | str, reason_key: str, message: str = ""
) -> None:
    return await report_peer(client, user_id, reason_key, message)


async def cmd_nuke(client: TelemanClient, peer_id: int | str) -> dict[str, object]:
    peer = await get_peer(client, peer_id)
    display = peer_name(peer)
    count = await delete_all_messages(client, peer_id)
    await delete_dialog(client, peer_id)
    return {"peer": display, "peer_id": peer.id, "deleted_messages": count}
