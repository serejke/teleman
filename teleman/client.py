from __future__ import annotations

from typing import Any

from telethon import TelegramClient

from teleman.config import AccountConfig


class TelemanClient:
    def __init__(
        self,
        account: AccountConfig,
        session_path: str,
        proxy_kwargs: dict[str, Any] | None = None,
    ) -> None:
        self._account = account
        kwargs: dict[str, Any] = {}
        if proxy_kwargs is not None:
            kwargs.update(proxy_kwargs)
        self._client = TelegramClient(
            session_path,
            account.app_id,
            account.app_hash,
            **kwargs,
        )

    @property
    def raw(self) -> TelegramClient:
        return self._client

    async def connect(self) -> None:
        await self._client.connect()
        if not await self._client.is_user_authorized():
            phone = self._account.phone
            print(f"Session not authorized. Sending login code to {phone}...")
            await self._client.send_code_request(phone)
            code = input("Enter the code you received: ")
            try:
                await self._client.sign_in(phone, code)
            except Exception:
                # 2FA may be required
                import getpass

                password = getpass.getpass("2FA password required: ")
                await self._client.sign_in(password=password)
            print("Authorized successfully.")

    async def disconnect(self) -> None:
        await self._client.disconnect()
