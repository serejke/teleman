"""Estimate LLM token counts for exported chat messages.

Outputs token estimates for different representations:
  - text_only: just message texts concatenated
  - structured: date + sender + text per message (what you'd feed an LLM)
  - by_date: daily token counts (structured format)
"""

from __future__ import annotations

from collections import defaultdict
from datetime import date

import tiktoken
from pydantic import BaseModel

from analysis.loader import Message

NAME = "tokens"
DESCRIPTION = "LLM token count estimates (text-only, structured, daily breakdown)"

ENCODING = tiktoken.get_encoding("cl100k_base")


class DayTokenCount(BaseModel):
    date: str
    messages: int
    tokens: int


class TokensResult(BaseModel):
    encoding: str
    note: str
    text_only_tokens: int
    structured_tokens: int
    total_messages: int
    avg_tokens_per_message: float
    by_date: list[DayTokenCount]


def _count_tokens(text: str) -> int:
    return len(ENCODING.encode(text))


def _format_structured(msg: Message) -> str:
    parts = [f"[{msg.date.strftime('%Y-%m-%d %H:%M')}]"]
    if msg.sender_name:
        parts.append(f"{msg.sender_name}:")
    if msg.text:
        parts.append(msg.text)
    if msg.media:
        parts.append(f"[{msg.media.type}]")
    return " ".join(parts)


def compute(messages: list[Message]) -> TokensResult:
    all_text = "\n".join(msg.text for msg in messages if msg.text)
    text_only_tokens = _count_tokens(all_text)

    structured_lines = [_format_structured(msg) for msg in messages]
    structured_tokens = _count_tokens("\n".join(structured_lines))

    daily: dict[date, list[str]] = defaultdict(list)
    for msg, line in zip(messages, structured_lines, strict=True):
        daily[msg.date.date()].append(line)

    by_date = [
        DayTokenCount(
            date=str(d),
            messages=len(daily[d]),
            tokens=_count_tokens("\n".join(daily[d])),
        )
        for d in sorted(daily.keys())
    ]

    return TokensResult(
        encoding="cl100k_base",
        note="Approximate. Claude tokenizer differs by ~5-15%.",
        text_only_tokens=text_only_tokens,
        structured_tokens=structured_tokens,
        total_messages=len(messages),
        avg_tokens_per_message=round(structured_tokens / len(messages), 1) if messages else 0,
        by_date=by_date,
    )
