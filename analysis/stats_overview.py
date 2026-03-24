"""Chat overview: totals, date range, high-level numbers."""

from __future__ import annotations

from pydantic import BaseModel

from analysis.loader import Message

NAME = "overview"
DESCRIPTION = "Total messages, text messages, symbols, date range"


class DateRange(BaseModel):
    first: str | None
    last: str | None


class OverviewResult(BaseModel):
    total_messages: int
    total_messages_with_text: int
    total_messages_with_media: int
    total_symbols: int
    total_forwards: int
    total_replies: int
    total_edits: int
    unique_senders: int
    date_range: DateRange


def compute(messages: list[Message]) -> OverviewResult:
    total_symbols = 0
    total_with_text = 0
    total_with_media = 0
    total_forwards = 0
    total_replies = 0
    total_edits = 0
    unique_senders: set[str] = set()

    for msg in messages:
        tlen = len(msg.text) if msg.text else 0
        if tlen > 0:
            total_with_text += 1
            total_symbols += tlen
        if msg.media:
            total_with_media += 1
        if msg.forward_from_id or msg.forward_from_name:
            total_forwards += 1
        if msg.reply_to_msg_id:
            total_replies += 1
        if msg.edit_date:
            total_edits += 1
        unique_senders.add(msg.sender_name or str(msg.sender_id))

    dates = [msg.date for msg in messages]
    return OverviewResult(
        total_messages=len(messages),
        total_messages_with_text=total_with_text,
        total_messages_with_media=total_with_media,
        total_symbols=total_symbols,
        total_forwards=total_forwards,
        total_replies=total_replies,
        total_edits=total_edits,
        unique_senders=len(unique_senders),
        date_range=DateRange(
            first=str(min(dates).date()) if dates else None,
            last=str(max(dates).date()) if dates else None,
        ),
    )
