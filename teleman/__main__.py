from __future__ import annotations

import asyncio
import sys
from pathlib import Path

from dotenv import load_dotenv

from teleman.cli import run
from teleman.client import TelemanClient
from teleman.config import Settings, list_accounts, load_account
from teleman.proxy import get_proxy_for_account, load_proxies


def _parse_account_arg() -> str | None:
    args = sys.argv[1:]
    for i, arg in enumerate(args):
        if arg == "--account" and i + 1 < len(args):
            return args[i + 1]
    return None


def _pick_account(accounts_dir: str) -> str:
    accounts = list_accounts(accounts_dir)
    if not accounts:
        print(f"No accounts found in {accounts_dir}/")
        sys.exit(1)
    if len(accounts) == 1:
        return accounts[0]
    print("Available accounts:")
    for idx, name in enumerate(accounts, 1):
        print(f"  {idx}. {name}")
    choice = input("Select account number: ").strip()
    try:
        return accounts[int(choice) - 1]
    except (ValueError, IndexError):
        print("Invalid selection.")
        sys.exit(1)


async def main() -> None:
    load_dotenv()
    settings = Settings()  # type: ignore[call-arg]

    account_name = _parse_account_arg()
    if account_name is None:
        account_name = _pick_account(settings.accounts_dir)

    account = load_account(settings.accounts_dir, account_name)
    session_path = str(Path(settings.accounts_dir) / account_name)

    proxies = load_proxies(settings.accounts_dir)
    if proxies:
        proxy_config = get_proxy_for_account(proxies, account_name)
    else:
        proxy_config = None
    proxy_kwargs = proxy_config.to_telethon_kwargs() if proxy_config else None
    if proxy_config is not None:
        print(f"Using {proxy_config.type} proxy {proxy_config.addr}:{proxy_config.port}")
    elif proxies:
        print("Direct connection (no proxy)")

    client = TelemanClient(account, session_path, proxy_kwargs=proxy_kwargs)
    await client.connect()
    try:
        await run(client)
    finally:
        await client.disconnect()


if __name__ == "__main__":
    asyncio.run(main())
