from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING, Any

from pydantic import BaseModel
from telethon.tl.functions.account import (
    GetAccountTTLRequest,
    GetPasswordRequest,
    GetWebAuthorizationsRequest,
    ResetWebAuthorizationRequest,
    ResetWebAuthorizationsRequest,
    SetAccountTTLRequest,
)
from telethon.tl.types import AccountDaysTTL

if TYPE_CHECKING:
    from teleman.client import TelemanClient


class TwoFactorStatus(BaseModel):
    enabled: bool
    has_recovery_email: bool

    @classmethod
    def from_telethon(cls, obj: Any) -> TwoFactorStatus:
        return cls(
            enabled=obj.has_password or False,
            has_recovery_email=bool(
                getattr(obj, "email_unconfirmed_pattern", None)
                or getattr(obj, "has_recovery", False)
            ),
        )


class AccountTTL(BaseModel):
    days: int

    @classmethod
    def from_telethon(cls, obj: Any) -> AccountTTL:
        return cls(days=obj.days)


class WebSession(BaseModel):
    hash: int
    domain: str
    browser: str
    platform: str
    ip: str
    region: str
    date_created: datetime
    date_active: datetime
    bot_name: str

    @classmethod
    def from_telethon(cls, obj: Any) -> WebSession:
        return cls(
            hash=obj.hash,
            domain=obj.domain or "",
            browser=obj.browser or "",
            platform=obj.platform or "",
            ip=obj.ip or "",
            region=obj.region or "",
            date_created=obj.date_created,
            date_active=obj.date_active,
            bot_name=getattr(obj, "bot_name", "") or "",
        )


async def get_2fa_status(client: TelemanClient) -> TwoFactorStatus:
    result = await client.raw(GetPasswordRequest())
    return TwoFactorStatus.from_telethon(result)


async def get_account_ttl(client: TelemanClient) -> AccountTTL:
    result = await client.raw(GetAccountTTLRequest())
    return AccountTTL.from_telethon(result)


async def set_account_ttl(client: TelemanClient, days: int) -> AccountTTL:
    await client.raw(SetAccountTTLRequest(ttl=AccountDaysTTL(days=days)))
    return await get_account_ttl(client)


async def get_web_sessions(client: TelemanClient) -> list[WebSession]:
    result = await client.raw(GetWebAuthorizationsRequest())
    return [WebSession.from_telethon(auth) for auth in result.authorizations]


async def end_web_session(client: TelemanClient, session_hash: int) -> bool:
    result = await client.raw(ResetWebAuthorizationRequest(hash=session_hash))
    return bool(result)


async def end_all_web_sessions(client: TelemanClient) -> bool:
    result = await client.raw(ResetWebAuthorizationsRequest())
    return bool(result)
