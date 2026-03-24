from __future__ import annotations

from pydantic import BaseModel
from telethon.tl.functions.account import GetPrivacyRequest, SetPrivacyRequest
from telethon.tl.types import (
    InputPrivacyKeyAbout,
    InputPrivacyKeyBirthday,
    InputPrivacyKeyChatInvite,
    InputPrivacyKeyForwards,
    InputPrivacyKeyPhoneCall,
    InputPrivacyKeyPhoneNumber,
    InputPrivacyKeyProfilePhoto,
    InputPrivacyKeyStatusTimestamp,
    InputPrivacyKeyVoiceMessages,
    InputPrivacyValueAllowAll,
    InputPrivacyValueAllowContacts,
    InputPrivacyValueDisallowAll,
    PrivacyValueAllowAll,
    PrivacyValueAllowCloseFriends,
    PrivacyValueAllowContacts,
    PrivacyValueDisallowAll,
)

from teleman.client import TelemanClient

PRIVACY_KEYS: list[tuple[str, type]] = [
    ("phone_number", InputPrivacyKeyPhoneNumber),
    ("last_seen", InputPrivacyKeyStatusTimestamp),
    ("profile_photo", InputPrivacyKeyProfilePhoto),
    ("bio", InputPrivacyKeyAbout),
    ("birthday", InputPrivacyKeyBirthday),
    ("forwards", InputPrivacyKeyForwards),
    ("calls", InputPrivacyKeyPhoneCall),
    ("groups", InputPrivacyKeyChatInvite),
    ("voice_messages", InputPrivacyKeyVoiceMessages),
]

PRIVACY_KEY_LABELS: dict[str, str] = {
    "phone_number": "Phone number",
    "last_seen": "Last seen",
    "profile_photo": "Profile photo",
    "bio": "Bio",
    "birthday": "Birthday",
    "forwards": "Forwards",
    "calls": "Calls",
    "groups": "Groups",
    "voice_messages": "Voice messages",
}

LEVEL_RULES = {
    "everyone": [InputPrivacyValueAllowAll()],
    "contacts": [InputPrivacyValueAllowContacts()],
    "nobody": [InputPrivacyValueDisallowAll()],
}


class PrivacyRule(BaseModel):
    key: str
    label: str
    level: str
    error: str | None = None


def _describe_rules(rules: list[object]) -> str:
    for r in rules:
        if isinstance(r, PrivacyValueAllowAll):
            return "everyone"
        if isinstance(r, PrivacyValueAllowContacts):
            return "contacts"
        if isinstance(r, PrivacyValueDisallowAll):
            return "nobody"
        if isinstance(r, PrivacyValueAllowCloseFriends):
            return "close_friends"
    return "unknown"


async def get_privacy(client: TelemanClient) -> list[PrivacyRule]:
    results: list[PrivacyRule] = []
    for key_name, key_cls in PRIVACY_KEYS:
        try:
            resp = await client.raw(GetPrivacyRequest(key_cls()))
            level = _describe_rules(resp.rules)
        except Exception:
            level = "error"
        results.append(
            PrivacyRule(
                key=key_name,
                label=PRIVACY_KEY_LABELS[key_name],
                level=level,
            )
        )
    return results


async def set_privacy(
    client: TelemanClient,
    key_name: str,
    level: str,
) -> PrivacyRule:
    key_cls = dict(PRIVACY_KEYS).get(key_name)
    if key_cls is None:
        raise ValueError(f"Unknown privacy key: {key_name}")
    rules = LEVEL_RULES.get(level)
    if rules is None:
        raise ValueError(f"Unknown level: {level}. Use: everyone, contacts, nobody")
    resp = await client.raw(SetPrivacyRequest(key=key_cls(), rules=rules))
    return PrivacyRule(
        key=key_name,
        label=PRIVACY_KEY_LABELS[key_name],
        level=_describe_rules(resp.rules),
    )


async def lockdown_privacy(client: TelemanClient) -> list[PrivacyRule]:
    """Set all privacy settings to the most restrictive level (nobody)."""
    results: list[PrivacyRule] = []
    for key_name, _ in PRIVACY_KEYS:
        try:
            result = await set_privacy(client, key_name, "nobody")
        except Exception as exc:
            result = PrivacyRule(
                key=key_name,
                label=PRIVACY_KEY_LABELS[key_name],
                level="skipped",
                error=str(exc),
            )
        results.append(result)
    return results
