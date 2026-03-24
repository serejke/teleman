from __future__ import annotations

import re
from datetime import datetime

from pydantic import BaseModel

from teleman.export.models import ExportedMessage

URL_RE = re.compile(r"https?://[^\s<>\"')\]]+")


class ExtractedLink(BaseModel):
    url: str
    message_id: int
    date: datetime
    sender_id: int | None = None
    sender_name: str | None = None


def extract_links(
    messages: list[ExportedMessage],
    *,
    after: datetime | None = None,
    before: datetime | None = None,
) -> list[ExtractedLink]:
    """Extract all URLs from exported messages, optionally filtered by date range."""
    links: list[ExtractedLink] = []
    seen: set[tuple[int, str]] = set()

    for msg in messages:
        date_naive = msg.date.replace(tzinfo=None)
        if after is not None and date_naive < after:
            continue
        if before is not None and date_naive >= before:
            continue

        for url in _extract_urls(msg):
            key = (msg.id, url)
            if key not in seen:
                seen.add(key)
                links.append(
                    ExtractedLink(
                        url=url,
                        message_id=msg.id,
                        date=msg.date,
                        sender_id=msg.sender_id,
                        sender_name=msg.sender_name,
                    )
                )

    return links


def _extract_urls(msg: ExportedMessage) -> list[str]:
    """Extract URLs from message entities and text."""
    urls: list[str] = []
    text = msg.text or ""

    if msg.entities:
        for ent in msg.entities:
            if ent.type == "url":
                urls.append(text[ent.offset : ent.offset + ent.length])
            elif ent.type == "texturl" and ent.url:
                urls.append(ent.url)

    # Fallback: regex on text if no entities found URLs
    if not urls and text:
        urls.extend(URL_RE.findall(text))

    return urls
