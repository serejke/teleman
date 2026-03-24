"""Temporal activity patterns: by date, hour of day, day of week."""

from __future__ import annotations

from collections import defaultdict
from datetime import date

from pydantic import BaseModel

from analysis.loader import Message

NAME = "activity"
DESCRIPTION = "Message counts by date, hour of day, and day of week"

_DOW_NAMES = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]


class DayCount(BaseModel):
    date: str
    messages: int


class HourCount(BaseModel):
    hour: int
    messages: int


class DowCount(BaseModel):
    day: str
    day_index: int
    messages: int


class ActivityResult(BaseModel):
    by_date: list[DayCount]
    by_hour: list[HourCount]
    by_day_of_week: list[DowCount]
    most_active_date: str | None
    most_active_hour: int | None
    most_active_day: str | None


def compute(messages: list[Message]) -> ActivityResult:
    daily: dict[date, int] = defaultdict(int)
    hourly: dict[int, int] = defaultdict(int)
    dow: dict[int, int] = defaultdict(int)

    for msg in messages:
        dt = msg.date
        daily[dt.date()] += 1
        hourly[dt.hour] += 1
        dow[dt.weekday()] += 1

    sorted_dates = sorted(daily.keys())

    return ActivityResult(
        by_date=[DayCount(date=str(d), messages=daily[d]) for d in sorted_dates],
        by_hour=[HourCount(hour=h, messages=hourly.get(h, 0)) for h in range(24)],
        by_day_of_week=[DowCount(day=_DOW_NAMES[d], day_index=d, messages=dow.get(d, 0)) for d in range(7)],
        most_active_date=str(max(daily, key=daily.get)) if daily else None,
        most_active_hour=max(hourly, key=hourly.get) if hourly else None,
        most_active_day=_DOW_NAMES[max(dow, key=dow.get)] if dow else None,
    )
