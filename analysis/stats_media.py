"""Media breakdown: types, top senders, file sizes."""

from __future__ import annotations

from collections import defaultdict

from pydantic import BaseModel

from analysis.loader import Message

NAME = "media"
DESCRIPTION = "Media type distribution, top media senders, file size stats"


class MediaTypeCount(BaseModel):
    type: str
    count: int


class MediaSenderCount(BaseModel):
    sender_name: str
    media_count: int


class FileSizeStats(BaseModel):
    total_bytes: int
    total_mb: float
    count_with_size: int
    avg_bytes: int


class MediaResult(BaseModel):
    total_media_messages: int
    by_type: list[MediaTypeCount]
    top_senders: list[MediaSenderCount]
    file_sizes: FileSizeStats


def compute(messages: list[Message], *, top_n: int = 20) -> MediaResult:
    by_type: dict[str, int] = defaultdict(int)
    by_sender: dict[str, int] = defaultdict(int)
    sizes: list[int] = []

    for msg in messages:
        if not msg.media:
            continue
        by_type[msg.media.type] += 1
        sender = msg.sender_name or str(msg.sender_id)
        by_sender[sender] += 1
        if msg.media.size is not None:
            sizes.append(msg.media.size)

    total_media = sum(by_type.values())
    total_size = sum(sizes)

    return MediaResult(
        total_media_messages=total_media,
        by_type=[MediaTypeCount(type=t, count=c) for t, c in sorted(by_type.items(), key=lambda x: -x[1])],
        top_senders=[
            MediaSenderCount(sender_name=name, media_count=count)
            for name, count in sorted(by_sender.items(), key=lambda x: -x[1])[:top_n]
        ],
        file_sizes=FileSizeStats(
            total_bytes=total_size,
            total_mb=round(total_size / 1_048_576, 1),
            count_with_size=len(sizes),
            avg_bytes=round(total_size / len(sizes)) if sizes else 0,
        ),
    )
