from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel
from telethon.tl.functions.account import GetAuthorizationsRequest, ResetAuthorizationRequest

from teleman.client import TelemanClient


class Session(BaseModel):
    hash: int
    current: bool
    device_model: str
    platform: str
    system_version: str
    app_name: str
    app_version: str
    ip: str
    country: str
    date_created: datetime
    date_active: datetime
    official_app: bool

    @classmethod
    def from_telethon(cls, obj: Any) -> Session:
        return cls(
            hash=obj.hash,
            current=obj.current or False,
            device_model=obj.device_model or "",
            platform=obj.platform or "",
            system_version=obj.system_version or "",
            app_name=obj.app_name or "",
            app_version=obj.app_version or "",
            ip=obj.ip or "",
            country=obj.country or "",
            date_created=obj.date_created,
            date_active=obj.date_active,
            official_app=obj.official_app or False,
        )


async def get_sessions(client: TelemanClient) -> list[Session]:
    result = await client.raw(GetAuthorizationsRequest())
    return [Session.from_telethon(auth) for auth in result.authorizations]


async def end_session(client: TelemanClient, session_hash: int) -> bool:
    return await client.raw(ResetAuthorizationRequest(hash=session_hash))
