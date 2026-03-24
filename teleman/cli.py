from __future__ import annotations

import asyncio
import readline  # noqa: F401 — enables arrow-key history in input()
import shutil
import textwrap
from typing import Any
from urllib.parse import parse_qs, urlparse

from teleman.client import TelemanClient
from teleman.contacts import add_contact, get_peer, get_user, peer_name
from teleman.export.exporter import export_chat
from teleman.export.resolver import list_dialogs
from teleman.messages import delete_all_messages, delete_dialog, get_raw_messages, send_message
from teleman.models import Group, Message, User


def _sender_display_name(raw_sender: Any) -> str:
    if raw_sender is None:
        return "?"
    if hasattr(raw_sender, "first_name"):
        return raw_sender.first_name or "?"
    if hasattr(raw_sender, "title"):
        return raw_sender.title or "?"
    return "?"


def _format_message(msg: Message, my_name: str, sender_name: str, width: int) -> str:
    name = my_name if msg.out else sender_name
    header = f"{name} · {msg.date:%m/%d %H:%M} UTC"
    max_text_width = max(width // 2, 20)
    text = msg.text or ""
    lines = textwrap.wrap(text, width=max_text_width) if text else [""]

    if msg.out:
        formatted = [header.rjust(width)]
        for line in lines:
            formatted.append(line.rjust(width))
    else:
        indent = "  "
        formatted = [f"{indent}{header}"]
        for line in lines:
            formatted.append(f"{indent}{line}")
    return "\n".join(formatted)


def _get_button_rows(raw_msg: Any) -> list[list[Any]] | None:
    """Extract button rows from a message, falling back to reply_markup if needed.

    Telethon's message.buttons can return None in groups when input_chat
    or the bot sender can't be resolved. Fall back to reply_markup.rows
    which is always available on the raw message object.
    """
    buttons = getattr(raw_msg, "buttons", None)
    if buttons:
        return buttons
    reply_markup = getattr(raw_msg, "reply_markup", None)
    if reply_markup:
        rows = getattr(reply_markup, "rows", None)
        if rows:
            return [row.buttons for row in rows]
    return None


def _format_buttons(raw_msg: Any) -> str | None:
    rows = _get_button_rows(raw_msg)
    if not rows:
        return None
    parts: list[str] = []
    idx = 1
    for row in rows:
        row_parts: list[str] = []
        for button in row:
            row_parts.append(f"[{idx}] {button.text}")
            idx += 1
        parts.append("  " + "  ".join(row_parts))
    return "\n".join(parts)


def _button_count(raw_msg: Any) -> int:
    rows = _get_button_rows(raw_msg)
    if not rows:
        return 0
    return sum(len(row) for row in rows)


async def _input(prompt: str) -> str:
    return await asyncio.to_thread(input, prompt)


def _parse_user_id(raw: str) -> int | str:
    """Parse a user identifier: numeric ID or @username."""
    try:
        return int(raw)
    except ValueError:
        return raw


def _parse_tme_link(raw: str) -> tuple[str, str | None] | None:
    """Parse a t.me deep link, returning (username, start_param | None).

    Supports https://t.me/bot?start=param and http://t.me/bot?start=param.
    Returns None if the input is not a t.me link.
    """
    try:
        parsed = urlparse(raw)
    except ValueError:
        return None
    if parsed.hostname not in ("t.me", "www.t.me"):
        return None
    path = parsed.path.strip("/")
    if not path:
        return None
    username = path.split("/")[0]
    qs = parse_qs(parsed.query)
    start_param = qs.get("start", [None])[0]
    return username, start_param


async def _cmd_chat(
    client: TelemanClient,
    user_id: int | str,
    limit: int = 20,
    start_param: str | None = None,
) -> None:
    from telethon import events
    from telethon.errors import ChatWriteForbiddenError, SlowModeWaitError, UserBannedInChannelError
    from telethon.tl.functions.messages import StartBotRequest

    peer = await get_peer(client, user_id)

    if start_param and not isinstance(peer, Group):
        await client.raw(StartBotRequest(bot=peer.id, peer=peer.id, start_param=start_param))
    is_group = isinstance(peer, Group)
    display = peer_name(peer)
    width = shutil.get_terminal_size((80, 24)).columns
    my_name = "You"

    sender_names: dict[int, str] = {}

    def _get_sender_name(msg: Message, raw_msg: Any) -> str:
        if msg.out:
            return my_name
        if not is_group:
            return display
        sid = msg.sender_id
        if sid in sender_names:
            return sender_names[sid]
        name = _sender_display_name(getattr(raw_msg, "sender", None))
        sender_names[sid] = name
        return name

    last_buttons_msg: dict[str, Any] = {"raw": None}

    def _print_msg_with_buttons(
        msg: Message,
        raw_msg: Any,
        *,
        edited: bool = False,
    ) -> None:
        prefix = "[edited] " if edited else ""
        sender = _get_sender_name(msg, raw_msg)
        text = _format_message(msg, my_name, sender, width)
        if prefix:
            lines = text.split("\n")
            lines[0] = f"  {prefix}{lines[0].lstrip()}"
            text = "\n".join(lines)
        btn_text = _format_buttons(raw_msg)
        if btn_text:
            text += "\n" + btn_text
            last_buttons_msg["raw"] = raw_msg
        print(f"\r\033[K{text}\n")

    def _print_incoming(msg: Message, raw_msg: Any, *, edited: bool = False) -> None:
        _print_msg_with_buttons(msg, raw_msg, edited=edited)
        print(f"{peer.id}> ", end="", flush=True)

    if is_group:

        @client.raw.on(events.NewMessage(chats=[peer.id]))
        async def _on_new_message(event: events.NewMessage.Event) -> None:
            msg = Message.from_telethon(event.message)
            if not msg.out:
                _print_incoming(msg, event.message)

        @client.raw.on(events.MessageEdited(chats=[peer.id]))
        async def _on_message_edited(event: events.MessageEdited.Event) -> None:
            msg = Message.from_telethon(event.message)
            if not msg.out:
                _print_incoming(msg, event.message, edited=True)
    else:

        @client.raw.on(events.NewMessage(from_users=[peer.id]))
        async def _on_new_message(event: events.NewMessage.Event) -> None:
            msg = Message.from_telethon(event.message)
            if not msg.out:
                _print_incoming(msg, event.message)

        @client.raw.on(events.MessageEdited(from_users=[peer.id]))
        async def _on_message_edited(event: events.MessageEdited.Event) -> None:
            msg = Message.from_telethon(event.message)
            if not msg.out:
                _print_incoming(msg, event.message, edited=True)

    print(f"Chatting with {display} (ID: {peer.id}). Empty line to exit. #N to click button N.")
    raw_messages = await get_raw_messages(client, user_id, limit=limit)
    for raw_msg in reversed(raw_messages):
        msg = Message.from_telethon(raw_msg)
        _print_msg_with_buttons(msg, raw_msg)
    await client.raw.catch_up()
    try:
        while True:
            text = await _input(f"{peer.id}> ")
            if not text:
                break
            if text.startswith("#"):
                try:
                    n = int(text[1:])
                except ValueError:
                    print("Usage: #N (e.g. #1 to click button 1)")
                    continue
                raw = last_buttons_msg["raw"]
                if raw is None:
                    print("No buttons to click.")
                    continue
                total = _button_count(raw)
                if n < 1 or n > total:
                    print(f"Button number must be between 1 and {total}.")
                    continue
                await raw.click(i=n - 1)
                continue
            try:
                msg = await send_message(client, user_id, text)
            except ChatWriteForbiddenError:
                print("You don't have permission to write in this chat.")
                continue
            except SlowModeWaitError as e:
                print(f"Slow mode active. Wait {e.seconds}s before sending again.")
                continue
            except UserBannedInChannelError:
                print("You are banned from sending messages in this chat.")
                continue
            print(_format_message(msg, my_name, my_name, width))
            print()
    finally:
        client.raw.remove_event_handler(_on_new_message)
        client.raw.remove_event_handler(_on_message_edited)


async def _cmd_add(client: TelemanClient, user_id: int | str) -> None:
    user = await add_contact(client, user_id)
    print(f"Added contact: {user.first_name} (ID: {user.id})")


async def _cmd_me(client: TelemanClient) -> None:

    raw_me = await client.raw.get_me()
    me = User.from_telethon(raw_me)
    name = me.first_name
    if me.last_name:
        name += f" {me.last_name}"
    print(f"  Name:     {name}")
    print(f"  ID:       {me.id}")
    print(f"  Phone:    {me.phone or 'N/A'}")
    print(f"  Username: @{me.username}" if me.username else "  Username: N/A")
    print(f"  Premium:  {'Yes' if me.premium else 'No'}")


async def _cmd_privacy(client: TelemanClient, *, hint: bool = False) -> None:
    from teleman.privacy import get_privacy

    rules = await get_privacy(client)
    for r in rules:
        print(f"  {r.label:20s} {r.level}")
    if hint:
        print("  Tip: use /settings for an overview")


async def _cmd_privacy_set(client: TelemanClient, key: str, level: str) -> None:
    from teleman.privacy import set_privacy

    result = await set_privacy(client, key, level)
    print(f"  {result.label}: {result.level}")


async def _cmd_lockdown(client: TelemanClient) -> None:
    from teleman.privacy import lockdown_privacy

    results = await lockdown_privacy(client)
    for r in results:
        if r.error:
            print(f"  {r.label:20s} SKIPPED ({r.error})")
        else:
            print(f"  {r.label:20s} {r.level}")


async def _cmd_chats(client: TelemanClient) -> None:
    dialogs = await client.raw.get_dialogs()
    for d in dialogs:
        entity = d.entity
        username_str = f" @{entity.username}" if getattr(entity, "username", None) else ""
        if hasattr(entity, "first_name"):
            kind = "user"
        elif hasattr(entity, "title"):
            is_group = getattr(entity, "megagroup", False) or not getattr(entity, "broadcast", False)
            kind = "group" if is_group else "channel"
        else:
            kind = "?"
        unread = f" [{d.unread_count} unread]" if d.unread_count else ""
        print(f"  {entity.id}{username_str} ({kind}){unread}")


async def _cmd_contacts(client: TelemanClient) -> None:
    from telethon.tl.functions.contacts import GetContactsRequest

    result = await client.raw(GetContactsRequest(hash=0))
    for u in result.users:
        user = User.from_telethon(u)
        name = user.first_name
        if user.last_name:
            name += f" {user.last_name}"
        username_str = f" @{user.username}" if user.username else ""
        print(f"  {user.id}: {name}{username_str}")


async def _cmd_sessions(client: TelemanClient, *, hint: bool = False) -> None:
    from teleman.sessions import get_sessions

    sessions = await get_sessions(client)
    for s in sessions:
        current_marker = " (current)" if s.current else ""
        official = " [official]" if s.official_app else ""
        print(
            f"  {s.device_model} — {s.platform} {s.system_version}"
            f"  |  {s.app_name} {s.app_version}{official}"
            f"  |  {s.ip} ({s.country})"
            f"  |  active {s.date_active:%Y-%m-%d %H:%M} UTC"
            f"  |  hash: {s.hash}{current_marker}"
        )
    if hint:
        print("  Tip: use /settings for an overview")


async def _cmd_web_sessions(client: TelemanClient) -> None:
    from teleman.settings import get_web_sessions

    sessions = await get_web_sessions(client)
    if not sessions:
        print("  No active web sessions.")
        return
    for s in sessions:
        print(
            f"  {s.domain} — {s.browser} on {s.platform}"
            f"  |  {s.ip} ({s.region})"
            f"  |  bot: {s.bot_name}"
            f"  |  active {s.date_active:%Y-%m-%d %H:%M} UTC"
            f"  |  hash: {s.hash}"
        )


async def _cmd_web_end(client: TelemanClient, session_hash: int) -> None:
    from teleman.settings import end_web_session, get_web_sessions

    sessions = await get_web_sessions(client)
    target = next((s for s in sessions if s.hash == session_hash), None)
    if target is None:
        print(f"No web session found with hash {session_hash}.")
        return
    await end_web_session(client, session_hash)
    print(f"Web session {session_hash} ({target.domain}) terminated.")


async def _cmd_web_end_all(client: TelemanClient) -> None:
    from teleman.settings import end_all_web_sessions

    await end_all_web_sessions(client)
    print("All web sessions terminated.")


async def _cmd_settings(client: TelemanClient, section: str | None = None) -> None:
    if section is None:
        await _cmd_settings_overview(client)
    elif section == "2fa":
        await _cmd_settings_2fa(client)
    elif section == "ttl":
        await _cmd_settings_ttl(client)
    elif section.startswith("ttl "):
        # /settings ttl <days>
        days_str = section[4:].strip()
        try:
            days = int(days_str)
        except ValueError:
            print("Usage: /settings ttl <days>")
            return
        await _cmd_settings_ttl_set(client, days)
    elif section == "privacy":
        await _cmd_privacy(client)
    elif section == "sessions":
        await _cmd_sessions(client)
    elif section == "web":
        await _cmd_web_sessions(client)
    else:
        print(f"Unknown settings section: {section}")
        print("Sections: 2fa, ttl, privacy, sessions, web")


async def _cmd_settings_overview(client: TelemanClient) -> None:
    from teleman.privacy import get_privacy
    from teleman.sessions import get_sessions
    from teleman.settings import get_2fa_status, get_account_ttl, get_web_sessions

    tfa = await get_2fa_status(client)
    ttl = await get_account_ttl(client)
    privacy_rules = await get_privacy(client)
    sessions = await get_sessions(client)
    web_sessions = await get_web_sessions(client)

    print("Settings overview:")
    print()
    tfa_status = "enabled" if tfa.enabled else "disabled"
    recovery = ", recovery email: yes" if tfa.has_recovery_email else ", recovery email: no"
    print(f"  2FA: {tfa_status}{recovery}")
    print(f"  Account TTL: {ttl.days} days")
    print()
    print("  Privacy:")
    for r in privacy_rules:
        print(f"    {r.label:20s} {r.level}")
    print()
    current = next((s for s in sessions if s.current), None)
    current_label = f", current: {current.device_model}" if current else ""
    print(f"  Sessions: {len(sessions)} total{current_label}")
    web_count = len(web_sessions)
    print(f"  Web sessions: {web_count}" if web_count else "  Web sessions: none")
    print()
    print("Use /settings <section> for details: 2fa, ttl, privacy, sessions, web")


async def _cmd_settings_2fa(client: TelemanClient) -> None:
    from teleman.settings import get_2fa_status

    tfa = await get_2fa_status(client)
    print(f"  2FA: {'enabled' if tfa.enabled else 'disabled'}")
    print(f"  Recovery email: {'yes' if tfa.has_recovery_email else 'no'}")


async def _cmd_settings_ttl(client: TelemanClient) -> None:
    from teleman.settings import get_account_ttl

    ttl = await get_account_ttl(client)
    print(f"  Account TTL: {ttl.days} days")
    print("  Use /settings ttl <days> to change")


async def _cmd_settings_ttl_set(client: TelemanClient, days: int) -> None:
    from teleman.settings import set_account_ttl

    ttl = await set_account_ttl(client, days)
    print(f"  Account TTL set to {ttl.days} days")


async def _cmd_session_end(client: TelemanClient, session_hash: int) -> None:
    from teleman.sessions import end_session, get_sessions

    sessions = await get_sessions(client)
    target = next((s for s in sessions if s.hash == session_hash), None)
    if target is None:
        print(f"No session found with hash {session_hash}.")
        return
    if target.current:
        print("Cannot terminate the current session.")
        return
    await end_session(client, session_hash)
    print(f"Session {session_hash} ({target.device_model}) terminated.")


async def _cmd_nuke(client: TelemanClient, user_id: int | str) -> None:
    peer = await get_peer(client, user_id)
    display = peer_name(peer)
    confirm = await _input(
        f"Delete ALL messages with {display} (ID: {peer.id}) for BOTH sides and remove chat? Type YES to confirm: "
    )
    if confirm.strip() != "YES":
        print("Aborted.")
        return
    count = await delete_all_messages(client, user_id)
    await delete_dialog(client, user_id)
    print(f"Deleted {count} messages and removed chat with {display}.")


async def _cmd_report(client: TelemanClient, user_id: int | str) -> None:
    from teleman.report import REPORT_REASONS, report_peer

    user = await get_user(client, user_id)
    print(f"Reporting {user.first_name} (ID: {user.id})")

    reason_keys = list(REPORT_REASONS.keys())
    for i, key in enumerate(reason_keys, 1):
        label, _ = REPORT_REASONS[key]
        print(f"  {i}. {label}")

    choice = await _input("Pick a reason number: ")
    try:
        idx = int(choice)
    except ValueError:
        print("Invalid choice.")
        return
    if idx < 1 or idx > len(reason_keys):
        print(f"Choice must be between 1 and {len(reason_keys)}.")
        return

    reason_key = reason_keys[idx - 1]
    message = await _input("Additional details (press Enter to skip): ")

    result = await report_peer(client, user_id, reason_key, message)
    print(f"Reported {result.user.first_name} for: {result.reason_label}")


async def _cmd_export_list(client: TelemanClient) -> None:
    dialogs = await list_dialogs(client)
    for i, (meta, _entity) in enumerate(dialogs, 1):
        print(f"  {i}. {meta.title} ({meta.type}, {meta.chat_id})")


async def _cmd_export(client: TelemanClient, query: str) -> None:
    def on_progress(count: int) -> None:
        print(f"\r  Exporting... {count} messages", end="", flush=True)

    title, count, incremental = await export_chat(client, query, on_progress)
    print()
    if incremental:
        print(f'  Synced {count} new messages from "{title}"')
    else:
        print(f'  Exported {count} messages from "{title}"')


async def run(client: TelemanClient) -> None:
    print("teleman — type /help for commands, /quit to exit")
    while True:
        try:
            line = await _input("teleman> ")
        except (EOFError, KeyboardInterrupt):
            break
        line = line.strip()
        if not line:
            continue
        parts = line.split()
        cmd = parts[0]
        args = parts[1:]
        try:
            if cmd == "/quit":
                break
            elif cmd == "/help":
                print("Commands:")
                print("  /me                       — show current account info")
                print("  /settings                 — security & privacy overview")
                print("  /settings 2fa             — 2FA status")
                print("  /settings ttl             — account TTL")
                print("  /settings ttl <days>      — set account TTL")
                print("  /settings privacy         — privacy settings")
                print("  /settings sessions        — active sessions")
                print("  /settings web             — web authorizations")
                print()
                print("  /privacy                  — show privacy settings")
                print("  /privacy_set <key> <lvl>  — set a privacy key (everyone/contacts/nobody)")
                print("  /lockdown                 — set all privacy to 'nobody'")
                print("  /sessions                 — list active sessions")
                print("  /session_end <hash>       — terminate a session by hash")
                print("  /web_end <hash>           — terminate a web session by hash")
                print("  /web_end_all              — terminate all web sessions")
                print()
                print("  /chat <peer> [n]          — chat with a user/group (show last n messages, default 20)")
                print("  /chat <t.me link>         — open a t.me deep link (sends /start param to bots)")
                print("  /add <user>               — add contact")
                print("  <peer>/<user> can be a numeric ID, @username, or t.me link")
                print("  /chats                    — list all chats")
                print("  /contacts                 — list contacts")
                print("  /nuke <peer>              — delete all messages (both sides) and remove chat")
                print("  /report <user>            — report a user for abuse")
                print()
                print("  /export_list              — list chats available for export")
                print("  /export <chat>            — export chat history (incremental)")
                print("  /quit                     — exit")
            elif cmd == "/me":
                await _cmd_me(client)
            elif cmd == "/settings":
                section = " ".join(args) if args else None
                await _cmd_settings(client, section)
            elif cmd == "/privacy":
                await _cmd_privacy(client, hint=True)
            elif cmd == "/privacy_set":
                if len(args) < 2:
                    print("Usage: /privacy_set <key> <everyone|contacts|nobody>")
                    continue
                await _cmd_privacy_set(client, args[0], args[1])
            elif cmd == "/lockdown":
                await _cmd_lockdown(client)
            elif cmd == "/chat":
                if not args:
                    print("Usage: /chat <peer> [limit]  or  /chat <t.me link>")
                    continue
                tme = _parse_tme_link(args[0])
                if tme:
                    username, start_param = tme
                    limit = int(args[1]) if len(args) > 1 else 20
                    await _cmd_chat(client, username, limit, start_param=start_param)
                else:
                    limit = int(args[1]) if len(args) > 1 else 20
                    await _cmd_chat(client, _parse_user_id(args[0]), limit)
            elif cmd == "/add":
                if not args:
                    print("Usage: /add <user>")
                    continue
                await _cmd_add(client, _parse_user_id(args[0]))
            elif cmd == "/chats":
                await _cmd_chats(client)
            elif cmd == "/contacts":
                await _cmd_contacts(client)
            elif cmd == "/sessions":
                await _cmd_sessions(client, hint=True)
            elif cmd == "/web_end":
                if not args:
                    print("Usage: /web_end <hash>")
                    continue
                try:
                    web_hash = int(args[0])
                except ValueError:
                    print("Web session hash must be a number.")
                    continue
                await _cmd_web_end(client, web_hash)
            elif cmd == "/web_end_all":
                await _cmd_web_end_all(client)
            elif cmd == "/session_end":
                if not args:
                    print("Usage: /session_end <hash>")
                    continue
                try:
                    session_hash = int(args[0])
                except ValueError:
                    print("Session hash must be a number.")
                    continue
                await _cmd_session_end(client, session_hash)
            elif cmd == "/nuke":
                if not args:
                    print("Usage: /nuke <user>")
                    continue
                await _cmd_nuke(client, _parse_user_id(args[0]))
            elif cmd == "/report":
                if not args:
                    print("Usage: /report <user>")
                    continue
                await _cmd_report(client, _parse_user_id(args[0]))
            elif cmd == "/export_list":
                await _cmd_export_list(client)
            elif cmd == "/export":
                if not args:
                    print("Usage: /export <chat name or ID>")
                    continue
                await _cmd_export(client, " ".join(args))
            else:
                print(f"Unknown command: {cmd}. Type /help for usage.")
        except Exception as exc:
            print(f"Error: {exc}")
