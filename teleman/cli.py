from __future__ import annotations

import asyncio
import readline  # noqa: F401 — enables arrow-key history in input()
import shutil
import textwrap
from datetime import datetime
from typing import Any
from urllib.parse import parse_qs, urlparse

from teleman.client import TelemanClient
from teleman.contacts import get_peer, peer_name
from teleman.messages import get_raw_messages, send_message
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


def _parse_date_flags(
    args: list[str],
    flags: tuple[str, str] = ("--after", "--before"),
) -> tuple[datetime | None, datetime | None, list[str]]:
    """Parse two date flags from args, return (after/since, before/until, remaining_args)."""
    after_flag, before_flag = flags
    after = None
    before = None
    remaining: list[str] = []
    i = 0
    while i < len(args):
        if args[i] == after_flag and i + 1 < len(args):
            after = datetime.strptime(args[i + 1], "%Y-%m-%d")
            i += 2
        elif args[i] == before_flag and i + 1 < len(args):
            before = datetime.strptime(args[i + 1], "%Y-%m-%d")
            i += 2
        else:
            remaining.append(args[i])
            i += 1
    return after, before, remaining


def _parse_user_id(raw: str) -> int | str:
    try:
        return int(raw)
    except ValueError:
        return raw


def _parse_tme_link(raw: str) -> tuple[str, str | None] | None:
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


# --- Formatting helpers for REPL display of response models ---


def _print_me(user: User) -> None:
    name = user.first_name
    if user.last_name:
        name += f" {user.last_name}"
    print(f"  Name:     {name}")
    print(f"  ID:       {user.id}")
    print(f"  Phone:    {user.phone or 'N/A'}")
    print(f"  Username: @{user.username}" if user.username else "  Username: N/A")
    print(f"  Premium:  {'Yes' if user.premium else 'No'}")


def _print_chats(resp: Any) -> None:
    for c in resp.chats:
        username_str = f" @{c.username}" if c.username else ""
        unread = f" [{c.unread_count} unread]" if c.unread_count else ""
        print(f"  {c.id}{username_str} ({c.type}){unread}")


def _print_contacts(resp: Any) -> None:
    for u in resp.contacts:
        name = u.first_name
        if u.last_name:
            name += f" {u.last_name}"
        username_str = f" @{u.username}" if u.username else ""
        print(f"  {u.id}: {name}{username_str}")


def _print_privacy(resp: Any, *, hint: bool = False) -> None:
    for r in resp.rules:
        print(f"  {r.label:20s} {r.level}")
    if hint:
        print("  Tip: use /settings for an overview")


def _print_lockdown(resp: Any) -> None:
    for r in resp.rules:
        if r.error:
            print(f"  {r.label:20s} SKIPPED ({r.error})")
        else:
            print(f"  {r.label:20s} {r.level}")


def _print_sessions(resp: Any, *, hint: bool = False) -> None:
    for s in resp.sessions:
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


def _print_web_sessions(resp: Any) -> None:
    if not resp.sessions:
        print("  No active web sessions.")
        return
    for s in resp.sessions:
        print(
            f"  {s.domain} — {s.browser} on {s.platform}"
            f"  |  {s.ip} ({s.region})"
            f"  |  bot: {s.bot_name}"
            f"  |  active {s.date_active:%Y-%m-%d %H:%M} UTC"
            f"  |  hash: {s.hash}"
        )


def _print_settings_overview(resp: Any) -> None:
    tfa_status = "enabled" if resp.two_factor.enabled else "disabled"
    recovery = ", recovery email: yes" if resp.two_factor.has_recovery_email else ", recovery email: no"
    print("Settings overview:")
    print()
    print(f"  2FA: {tfa_status}{recovery}")
    print(f"  Account TTL: {resp.account_ttl.days} days")
    print()
    print("  Privacy:")
    for r in resp.privacy:
        print(f"    {r.label:20s} {r.level}")
    print()
    current = next((s for s in resp.sessions if s.current), None)
    current_label = f", current: {current.device_model}" if current else ""
    print(f"  Sessions: {len(resp.sessions)} total{current_label}")
    web_count = len(resp.web_sessions)
    print(f"  Web sessions: {web_count}" if web_count else "  Web sessions: none")
    print()
    print("Use /settings <section> for details: 2fa, ttl, privacy, sessions, web")


# --- Interactive chat (stays in REPL only — requires event loop) ---


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


# --- Interactive report (stays in REPL — requires user prompts) ---


async def _cmd_report(client: TelemanClient, user_id: int | str) -> None:
    from teleman.contacts import get_user
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


# --- Interactive nuke (stays in REPL — requires confirmation) ---


async def _cmd_nuke(client: TelemanClient, user_id: int | str) -> None:
    from teleman.messages import delete_all_messages, delete_dialog

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


# --- REPL ---


async def run(client: TelemanClient) -> None:
    from teleman import commands

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
                print("  /export_list              — list chats available for sync")
                print("  /sync <chat> [--since DATE] [--until DATE] [--all-history]")
                print("                            — sync chat history (forward + backward fill)")
                print("  /sync --all               — sync every tracked chat")
                print("  /track <chat>             — mark a chat as tracked")
                print("  /untrack <chat>           — unmark a chat from batch sync")
                print("  /tracked                  — list tracked chats")
                print("  /checkpoints <chat>       — list sync checkpoints for a chat")
                print("  /links <chat> [--after YYYY-MM-DD] [--before YYYY-MM-DD]")
                print("                            — extract all links from a chat")
                print("  /quit                     — exit")
            elif cmd == "/me":
                _print_me(await commands.cmd_me(client))
            elif cmd == "/settings":
                section = " ".join(args) if args else None
                await _repl_settings(client, section)
            elif cmd == "/privacy":
                _print_privacy(await commands.cmd_privacy(client), hint=True)
            elif cmd == "/privacy_set":
                if len(args) < 2:
                    print("Usage: /privacy_set <key> <everyone|contacts|nobody>")
                    continue
                resp = await commands.cmd_privacy_set(client, args[0], args[1])
                for r in resp.rules:
                    print(f"  {r.label}: {r.level}")
            elif cmd == "/lockdown":
                _print_lockdown(await commands.cmd_lockdown(client))
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
                resp = await commands.cmd_add(client, _parse_user_id(args[0]))
                print(f"Added contact: {resp.user.first_name} (ID: {resp.user.id})")
            elif cmd == "/chats":
                _print_chats(await commands.cmd_chats(client))
            elif cmd == "/contacts":
                _print_contacts(await commands.cmd_contacts(client))
            elif cmd == "/sessions":
                _print_sessions(await commands.cmd_sessions(client), hint=True)
            elif cmd == "/web_end":
                if not args:
                    print("Usage: /web_end <hash>")
                    continue
                try:
                    web_hash = int(args[0])
                except ValueError:
                    print("Web session hash must be a number.")
                    continue
                resp = await commands.cmd_web_end(client, web_hash)
                print(f"Web session {resp.hash} ({resp.domain}) terminated.")
            elif cmd == "/web_end_all":
                await commands.cmd_web_end_all(client)
                print("All web sessions terminated.")
            elif cmd == "/session_end":
                if not args:
                    print("Usage: /session_end <hash>")
                    continue
                try:
                    session_hash = int(args[0])
                except ValueError:
                    print("Session hash must be a number.")
                    continue
                resp = await commands.cmd_session_end(client, session_hash)
                print(f"Session {resp.hash} ({resp.device_model}) terminated.")
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
                resp = await commands.cmd_export_list(client)
                for i, c in enumerate(resp.chats, 1):
                    print(f"  {i}. {c.title} ({c.type}, {c.chat_id})")
            elif cmd == "/sync":
                await _repl_sync(client, args)
            elif cmd == "/track":
                if not args:
                    print("Usage: /track <chat>")
                    continue
                resp = await commands.cmd_track(client, " ".join(args))
                print(f'  Tracking "{resp.title}" ({resp.chat_id})')
            elif cmd == "/untrack":
                if not args:
                    print("Usage: /untrack <chat>")
                    continue
                resp = await commands.cmd_untrack(client, " ".join(args))
                print(f'  Untracked "{resp.title}" ({resp.chat_id})')
            elif cmd == "/tracked":
                resp = commands.cmd_tracked()
                if not resp.chats:
                    print("  No tracked chats.")
                for c in resp.chats:
                    print(
                        f"  {c.title} ({c.chat_id}) — newest {c.newest_id}, "
                        f"synced {c.last_sync_date:%Y-%m-%d %H:%M} UTC"
                    )
            elif cmd == "/checkpoints":
                if not args:
                    print("Usage: /checkpoints <chat>")
                    continue
                resp = await commands.cmd_checkpoints(client, " ".join(args))
                print(f'  "{resp.title}" ({resp.chat_id}): {len(resp.checkpoints)} checkpoints')
                for cp in resp.checkpoints:
                    print(
                        f"    {cp.id:%Y-%m-%d %H:%M} UTC — +{cp.delta_count} msgs "
                        f"(id {cp.prev_newest_id} → {cp.newest_id})"
                    )
            elif cmd == "/links":
                if not args:
                    print("Usage: /links <chat> [--after YYYY-MM-DD] [--before YYYY-MM-DD]")
                    continue
                link_after, link_before, link_peer_parts = _parse_date_flags(args)
                if not link_peer_parts:
                    print("Usage: /links <chat> [--after YYYY-MM-DD] [--before YYYY-MM-DD]")
                    continue
                link_peer = " ".join(link_peer_parts)

                resp = commands.cmd_links(link_peer, after=link_after, before=link_before)
                for item in resp.links:
                    print(f"  {item.date:%Y-%m-%d %H:%M}  {item.url}")
                print(f"  Total: {resp.total} links")
            else:
                print(f"Unknown command: {cmd}. Type /help for usage.")
        except Exception as exc:
            print(f"Error: {exc}")


async def _repl_sync(client: TelemanClient, args: list[str]) -> None:
    from datetime import UTC

    from teleman import commands

    if "--all" in args:
        if len(args) > 1:
            print("Usage: /sync --all")
            return
        resp = await commands.cmd_sync_all(client)
        for r in resp.results:
            cp = f", checkpoint {r.checkpoint.id:%Y-%m-%d %H:%M}" if r.checkpoint is not None else ""
            print(f'  "{r.title}" ({r.chat_id}): +{r.new_count} new, {r.total_messages} total{cp}')
        for err in resp.errors:
            print(f"  ERROR {err.chat_id}: {err.error}")
        return

    all_history = "--all-history" in args
    filtered = [a for a in args if a != "--all-history"]
    after, before, chat_parts = _parse_date_flags(filtered, ("--since", "--until"))
    if not chat_parts:
        print("Usage: /sync <chat> [--since YYYY-MM-DD] [--until YYYY-MM-DD] [--all-history]")
        print("       /sync --all")
        return
    query = " ".join(chat_parts)
    since = after.replace(tzinfo=UTC) if after else None
    until = before.replace(tzinfo=UTC) if before else None

    def on_progress(new_count: int, backfill_count: int) -> None:
        print(
            f"\r  Syncing... +{new_count} new, +{backfill_count} backfilled",
            end="",
            flush=True,
        )

    from teleman.export.sync import sync_chat

    result = await sync_chat(
        client,
        query,
        since=since,
        until=until,
        all_history=all_history,
        on_progress=on_progress,
    )
    print()
    if result.bootstrap_required:
        print(
            f'  "{result.title}" has no export yet. Use /sync <chat> --since <date> '
            f"(or --all-history to fetch everything)."
        )
        return
    cp_str = f", checkpoint {result.checkpoint.id:%Y-%m-%d %H:%M}" if result.checkpoint is not None else ""
    print(
        f'  Synced "{result.title}": +{result.new_count} new, '
        f"+{result.backfilled_count} backfilled ({result.total_messages} total){cp_str}"
    )


async def _repl_settings(client: TelemanClient, section: str | None) -> None:
    from teleman import commands

    if section is None:
        _print_settings_overview(await commands.cmd_settings(client))
    elif section == "2fa":
        tfa = await commands.cmd_settings_2fa(client)
        print(f"  2FA: {'enabled' if tfa.enabled else 'disabled'}")
        print(f"  Recovery email: {'yes' if tfa.has_recovery_email else 'no'}")
    elif section == "ttl":
        ttl = await commands.cmd_settings_ttl(client)
        print(f"  Account TTL: {ttl.days} days")
        print("  Use /settings ttl <days> to change")
    elif section.startswith("ttl "):
        days_str = section[4:].strip()
        try:
            days = int(days_str)
        except ValueError:
            print("Usage: /settings ttl <days>")
            return
        ttl = await commands.cmd_settings_ttl_set(client, days)
        print(f"  Account TTL set to {ttl.days} days")
    elif section == "privacy":
        _print_privacy(await commands.cmd_privacy(client))
    elif section == "sessions":
        _print_sessions(await commands.cmd_sessions(client))
    elif section == "web":
        _print_web_sessions(await commands.cmd_web_sessions(client))
    else:
        print(f"Unknown settings section: {section}")
        print("Sections: 2fa, ttl, privacy, sessions, web")
