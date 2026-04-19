from __future__ import annotations

import argparse
import asyncio
import json
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from dotenv import load_dotenv
from pydantic import BaseModel

from teleman import commands
from teleman.cli import run as run_repl
from teleman.client import TelemanClient
from teleman.config import Settings, list_accounts, load_account
from teleman.proxy import get_proxy_for_account, load_proxies


def _parse_user_id(raw: str) -> int | str:
    try:
        return int(raw)
    except ValueError:
        return raw


def _parse_date(raw: str) -> datetime:
    return datetime.strptime(raw, "%Y-%m-%d").replace(tzinfo=UTC)


def _json_out(obj: Any) -> None:
    if isinstance(obj, BaseModel):
        print(obj.model_dump_json(indent=2))
    elif isinstance(obj, dict):
        print(json.dumps(obj, indent=2, default=str))
    else:
        print(json.dumps(obj, default=str))


def _pick_account(accounts_dir: str) -> str:
    accounts = list_accounts(accounts_dir)
    if not accounts:
        print(f"No accounts found in {accounts_dir}/", file=sys.stderr)
        sys.exit(1)
    if len(accounts) == 1:
        return accounts[0]
    print("Available accounts:", file=sys.stderr)
    for idx, name in enumerate(accounts, 1):
        print(f"  {idx}. {name}", file=sys.stderr)
    choice = input("Select account number: ").strip()
    try:
        return accounts[int(choice) - 1]
    except (ValueError, IndexError):
        print("Invalid selection.", file=sys.stderr)
        sys.exit(1)


async def _connect(settings: Settings, account_name: str | None) -> TelemanClient:
    if account_name is None:
        account_name = _pick_account(settings.accounts_dir)

    account = load_account(settings.accounts_dir, account_name)
    session_path = str(Path(settings.accounts_dir) / account_name)

    proxies = load_proxies(settings.accounts_dir)
    proxy_kwargs = None
    if proxies:
        proxy_config = get_proxy_for_account(proxies, account_name)
        if proxy_config:
            proxy_kwargs = proxy_config.to_telethon_kwargs()
            print(
                f"Using {proxy_config.type} proxy {proxy_config.addr}:{proxy_config.port}",
                file=sys.stderr,
            )
        else:
            print("Direct connection (no proxy)", file=sys.stderr)

    client = TelemanClient(account, session_path, proxy_kwargs=proxy_kwargs)
    await client.connect()
    return client


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="teleman", description="Telegram CLI client")
    parser.add_argument("--account", help="Account name to use")

    sub = parser.add_subparsers(dest="command")

    sub.add_parser("repl", help="Interactive REPL (default)")
    sub.add_parser("me", help="Show current account info")
    sub.add_parser("chats", help="List all chats")
    sub.add_parser("contacts", help="List contacts")

    p = sub.add_parser("messages", help="Get messages from a chat")
    p.add_argument("peer", help="Peer ID or @username")
    p.add_argument("--limit", type=int, default=20, help="Number of messages (default: 20)")

    p = sub.add_parser("send", help="Send a message")
    p.add_argument("peer", help="Peer ID or @username")
    p.add_argument("text", help="Message text")

    p = sub.add_parser("add", help="Add a contact")
    p.add_argument("user", help="User ID or @username")

    sub.add_parser("privacy", help="Show privacy settings")

    p = sub.add_parser("privacy-set", help="Set a privacy key")
    p.add_argument("key", help="Privacy key (e.g. phone_number, last_seen)")
    p.add_argument("level", choices=["everyone", "contacts", "nobody"], help="Privacy level")

    sub.add_parser("lockdown", help="Set all privacy to 'nobody'")
    sub.add_parser("sessions", help="List active sessions")

    p = sub.add_parser("session-end", help="Terminate a session by hash")
    p.add_argument("hash", type=int, help="Session hash")

    p = sub.add_parser("settings", help="Security & privacy overview")
    p.add_argument("section", nargs="?", help="Section: 2fa, ttl, privacy, sessions, web")
    p.add_argument("value", nargs="?", help="Value to set (e.g. days for ttl)")

    sub.add_parser("web-sessions", help="List web authorizations")

    p = sub.add_parser("web-end", help="Terminate a web session by hash")
    p.add_argument("hash", type=int, help="Web session hash")

    sub.add_parser("web-end-all", help="Terminate all web sessions")

    sub.add_parser("export-list", help="List chats available for export")

    p = sub.add_parser(
        "sync",
        help="Sync chat(s): forward catch-up + backward fill of missing history",
    )
    p.add_argument("chat", nargs="*", help="Chat name or ID (omit with --all)")
    p.add_argument(
        "--all", action="store_true", help="Sync every tracked chat (forward catch-up only)"
    )
    p.add_argument("--since", help="Stop the backward fill at this date (YYYY-MM-DD)")
    p.add_argument("--until", help="Filter out messages newer than this date (YYYY-MM-DD)")
    p.add_argument(
        "--all-history",
        action="store_true",
        help="Bootstrap a chat without --since by fetching full history (safety override)",
    )

    p = sub.add_parser("track", help="Mark a chat as tracked for batch sync")
    p.add_argument("chat", nargs="+", help="Chat name or ID")

    p = sub.add_parser("untrack", help="Unmark a chat from batch sync")
    p.add_argument("chat", nargs="+", help="Chat name or ID")

    sub.add_parser("tracked", help="List chats currently tracked for batch sync")

    p = sub.add_parser("checkpoints", help="List sync checkpoints for a chat")
    p.add_argument("chat", nargs="+", help="Chat name or ID")

    p = sub.add_parser("links", help="Extract all links from an exported chat")
    p.add_argument("chat", help="Chat ID, username, or title substring")
    p.add_argument("--after", help="Only links after this date (YYYY-MM-DD)")
    p.add_argument("--before", help="Only links before this date (YYYY-MM-DD)")

    return parser


async def _run_command(client: TelemanClient, args: argparse.Namespace) -> None:
    cmd = args.command

    if cmd == "me":
        _json_out(await commands.cmd_me(client))
    elif cmd == "chats":
        _json_out(await commands.cmd_chats(client))
    elif cmd == "contacts":
        _json_out(await commands.cmd_contacts(client))
    elif cmd == "messages":
        _json_out(await commands.cmd_messages(client, _parse_user_id(args.peer), limit=args.limit))
    elif cmd == "send":
        _json_out(await commands.cmd_send(client, _parse_user_id(args.peer), args.text))
    elif cmd == "add":
        _json_out(await commands.cmd_add(client, _parse_user_id(args.user)))
    elif cmd == "privacy":
        _json_out(await commands.cmd_privacy(client))
    elif cmd == "privacy-set":
        _json_out(await commands.cmd_privacy_set(client, args.key, args.level))
    elif cmd == "lockdown":
        _json_out(await commands.cmd_lockdown(client))
    elif cmd == "sessions":
        _json_out(await commands.cmd_sessions(client))
    elif cmd == "session-end":
        _json_out(await commands.cmd_session_end(client, args.hash))
    elif cmd == "settings":
        await _run_settings(client, args)
    elif cmd == "web-sessions":
        _json_out(await commands.cmd_web_sessions(client))
    elif cmd == "web-end":
        _json_out(await commands.cmd_web_end(client, args.hash))
    elif cmd == "web-end-all":
        _json_out(await commands.cmd_web_end_all(client))
    elif cmd == "export-list":
        _json_out(await commands.cmd_export_list(client))
    elif cmd == "sync":
        if args.all:
            if args.chat:
                raise ValueError("Pass either a chat or --all, not both")
            _json_out(await commands.cmd_sync_all(client))
        else:
            if not args.chat:
                raise ValueError("Usage: sync <chat> [--since DATE] [--until DATE] or sync --all")
            query = " ".join(args.chat)
            since = _parse_date(args.since) if args.since else None
            until = _parse_date(args.until) if args.until else None
            _json_out(
                await commands.cmd_sync(
                    client,
                    query,
                    since=since,
                    until=until,
                    all_history=args.all_history,
                )
            )
    elif cmd == "track":
        _json_out(await commands.cmd_track(client, " ".join(args.chat)))
    elif cmd == "untrack":
        _json_out(await commands.cmd_untrack(client, " ".join(args.chat)))
    elif cmd == "tracked":
        _json_out(commands.cmd_tracked())
    elif cmd == "checkpoints":
        _json_out(await commands.cmd_checkpoints(client, " ".join(args.chat)))
    elif cmd == "links":
        after = (
            datetime.strptime(args.after, "%Y-%m-%d").replace(tzinfo=UTC) if args.after else None
        )
        before = (
            datetime.strptime(args.before, "%Y-%m-%d").replace(tzinfo=UTC) if args.before else None
        )
        _json_out(commands.cmd_links(args.chat, after=after, before=before))


async def _run_settings(client: TelemanClient, args: argparse.Namespace) -> None:
    section = args.section
    if section is None:
        _json_out(await commands.cmd_settings(client))
    elif section == "2fa":
        _json_out(await commands.cmd_settings_2fa(client))
    elif section == "ttl":
        if args.value is not None:
            try:
                days = int(args.value)
            except ValueError:
                print('{"error": "ttl value must be an integer"}', file=sys.stderr)
                sys.exit(1)
            _json_out(await commands.cmd_settings_ttl_set(client, days))
        else:
            _json_out(await commands.cmd_settings_ttl(client))
    elif section == "privacy":
        _json_out(await commands.cmd_privacy(client))
    elif section == "sessions":
        _json_out(await commands.cmd_sessions(client))
    elif section == "web":
        _json_out(await commands.cmd_web_sessions(client))
    else:
        print(f'{{"error": "Unknown settings section: {section}"}}', file=sys.stderr)
        sys.exit(1)


async def main() -> None:
    load_dotenv()
    settings = Settings()

    parser = _build_parser()
    args = parser.parse_args()

    # Default to REPL when no subcommand given
    if args.command is None or args.command == "repl":
        client = await _connect(settings, args.account)
        try:
            await run_repl(client)
        finally:
            await client.disconnect()
        return

    client = await _connect(settings, args.account)
    try:
        await _run_command(client, args)
    except ValueError as exc:
        print(json.dumps({"error": str(exc)}), file=sys.stderr)
        sys.exit(1)
    except Exception as exc:
        print(json.dumps({"error": str(exc)}), file=sys.stderr)
        sys.exit(1)
    finally:
        await client.disconnect()


if __name__ == "__main__":
    asyncio.run(main())
