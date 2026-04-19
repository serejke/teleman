from __future__ import annotations

from typing import TYPE_CHECKING

from pydantic import BaseModel
from telethon.tl.functions.account import ReportPeerRequest
from telethon.tl.types import (
    InputReportReasonChildAbuse,
    InputReportReasonCopyright,
    InputReportReasonFake,
    InputReportReasonIllegalDrugs,
    InputReportReasonOther,
    InputReportReasonPersonalDetails,
    InputReportReasonPornography,
    InputReportReasonSpam,
    InputReportReasonViolence,
)

from teleman.contacts import get_user
from teleman.models import User

if TYPE_CHECKING:
    from teleman.client import TelemanClient

REPORT_REASONS: dict[str, tuple[str, type]] = {
    "spam": ("Spam", InputReportReasonSpam),
    "violence": ("Violence", InputReportReasonViolence),
    "pornography": ("Pornography", InputReportReasonPornography),
    "child_abuse": ("Child abuse", InputReportReasonChildAbuse),
    "copyright": ("Copyright", InputReportReasonCopyright),
    "fake": ("Fake account", InputReportReasonFake),
    "drugs": ("Illegal drugs", InputReportReasonIllegalDrugs),
    "personal_details": ("Personal details", InputReportReasonPersonalDetails),
    "other": ("Other", InputReportReasonOther),
}


class ReportResult(BaseModel):
    user: User
    reason_key: str
    reason_label: str
    message: str


async def report_peer(
    client: TelemanClient,
    user_id: int | str,
    reason_key: str,
    message: str = "",
) -> ReportResult:
    if reason_key not in REPORT_REASONS:
        valid = ", ".join(REPORT_REASONS)
        raise ValueError(f"Unknown reason: {reason_key}. Valid reasons: {valid}")

    label, reason_cls = REPORT_REASONS[reason_key]
    user = await get_user(client, user_id)
    entity = await client.raw.get_entity(user_id)

    await client.raw(
        ReportPeerRequest(
            peer=entity,
            reason=reason_cls(),
            message=message,
        )
    )

    return ReportResult(
        user=user,
        reason_key=reason_key,
        reason_label=label,
        message=message,
    )
