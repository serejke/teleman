from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel


class User(BaseModel):
    id: int
    first_name: str
    last_name: str | None = None
    username: str | None = None
    phone: str | None = None
    premium: bool = False

    @classmethod
    def from_telethon(cls, obj: Any) -> User:
        return cls(
            id=obj.id,
            first_name=obj.first_name or "",
            last_name=obj.last_name,
            username=obj.username,
            phone=getattr(obj, "phone", None),
            premium=getattr(obj, "premium", False) or False,
        )


class Group(BaseModel):
    id: int
    title: str
    username: str | None = None
    megagroup: bool = False
    broadcast: bool = False
    gigagroup: bool = False

    @classmethod
    def from_telethon(cls, obj: Any) -> Group:
        return cls(
            id=obj.id,
            title=obj.title or "",
            username=getattr(obj, "username", None),
            megagroup=getattr(obj, "megagroup", False) or False,
            broadcast=getattr(obj, "broadcast", False) or False,
            gigagroup=getattr(obj, "gigagroup", False) or False,
        )


Peer = User | Group


class Message(BaseModel):
    id: int
    sender_id: int
    chat_id: int
    text: str | None = None
    date: datetime
    out: bool

    @classmethod
    def from_telethon(cls, obj: Any) -> Message:
        return cls(
            id=obj.id,
            sender_id=obj.sender_id or 0,
            chat_id=obj.chat_id or 0,
            text=obj.text,
            date=obj.date,
            out=obj.out or False,
        )
