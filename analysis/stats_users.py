"""Per-user breakdown: messages, chars, media, avg length, active period."""

from __future__ import annotations

from collections import defaultdict

from pydantic import BaseModel

from analysis.loader import Message

NAME = "users"
DESCRIPTION = "Top users by messages, characters, media, avg message length"


class UserStats(BaseModel):
    sender_name: str
    messages: int
    text_messages: int
    symbols: int
    media: int
    replies: int
    forwards: int
    avg_message_length: float
    first_date: str | None
    last_date: str | None


class UsersResult(BaseModel):
    total_unique_senders: int
    top_n: int
    users: list[UserStats]


def compute(messages: list[Message], *, top_n: int = 50) -> UsersResult:
    acc: dict[str, list[int]] = defaultdict(lambda: [0, 0, 0, 0, 0, 0])
    # indices: messages, text_messages, symbols, media, replies, forwards
    first_dates: dict[str, str] = {}
    last_dates: dict[str, str] = {}

    for msg in messages:
        sender = msg.sender_name or str(msg.sender_id)
        s = acc[sender]
        s[0] += 1
        tlen = len(msg.text) if msg.text else 0
        if tlen > 0:
            s[1] += 1
            s[2] += tlen
        if msg.media:
            s[3] += 1
        if msg.reply_to_msg_id:
            s[4] += 1
        if msg.forward_from_id or msg.forward_from_name:
            s[5] += 1
        d = str(msg.date.date())
        if sender not in first_dates or d < first_dates[sender]:
            first_dates[sender] = d
        if sender not in last_dates or d > last_dates[sender]:
            last_dates[sender] = d

    ranked = sorted(acc.items(), key=lambda x: -x[1][0])[:top_n]

    return UsersResult(
        total_unique_senders=len(acc),
        top_n=top_n,
        users=[
            UserStats(
                sender_name=name,
                messages=s[0],
                text_messages=s[1],
                symbols=s[2],
                media=s[3],
                replies=s[4],
                forwards=s[5],
                avg_message_length=round(s[2] / s[1], 1) if s[1] else 0,
                first_date=first_dates.get(name),
                last_date=last_dates.get(name),
            )
            for name, s in ranked
        ],
    )
