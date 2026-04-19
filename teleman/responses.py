from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel

from teleman.export.models import Checkpoint
from teleman.models import Message, User
from teleman.privacy import PrivacyRule
from teleman.sessions import Session
from teleman.settings import AccountTTL, TwoFactorStatus, WebSession


class ChatInfo(BaseModel):
    id: int
    type: str  # "user", "group", "channel"
    username: str | None = None
    unread_count: int = 0


class ChatsResponse(BaseModel):
    chats: list[ChatInfo]


class ContactsResponse(BaseModel):
    contacts: list[User]


class MessagesResponse(BaseModel):
    peer_id: int | str
    messages: list[Message]


class SendResponse(BaseModel):
    message: Message


class AddContactResponse(BaseModel):
    user: User


class PrivacyResponse(BaseModel):
    rules: list[PrivacyRule]


class LockdownResponse(BaseModel):
    rules: list[PrivacyRule]


class SessionsResponse(BaseModel):
    sessions: list[Session]


class SessionEndResponse(BaseModel):
    hash: int
    device_model: str


class WebSessionsResponse(BaseModel):
    sessions: list[WebSession]


class WebEndResponse(BaseModel):
    hash: int
    domain: str


class WebEndAllResponse(BaseModel):
    pass


class SettingsOverview(BaseModel):
    two_factor: TwoFactorStatus
    account_ttl: AccountTTL
    privacy: list[PrivacyRule]
    sessions: list[Session]
    web_sessions: list[WebSession]


class ExportListItem(BaseModel):
    chat_id: int
    title: str
    type: str
    username: str | None = None


class ExportListResponse(BaseModel):
    chats: list[ExportListItem]


class SyncResponse(BaseModel):
    title: str
    new_count: int
    backfilled_count: int
    total_messages: int
    resumed: bool
    checkpoint: Checkpoint | None = None
    bootstrap_required: bool = False


class BatchSyncItem(BaseModel):
    chat_id: int
    title: str
    new_count: int
    backfilled_count: int
    total_messages: int
    resumed: bool
    checkpoint: Checkpoint | None = None


class BatchSyncError(BaseModel):
    chat_id: int
    title: str | None = None
    error: str


class BatchSyncResponse(BaseModel):
    results: list[BatchSyncItem]
    errors: list[BatchSyncError]


class TrackedChat(BaseModel):
    chat_id: int
    title: str
    type: str
    username: str | None = None
    newest_id: int
    last_sync_date: datetime


class TrackedResponse(BaseModel):
    chats: list[TrackedChat]


class TrackResponse(BaseModel):
    chat_id: int
    title: str
    tracked: bool


class CheckpointsResponse(BaseModel):
    chat_id: int
    title: str
    checkpoints: list[Checkpoint]


class LinkItem(BaseModel):
    url: str
    message_id: int
    date: datetime
    sender_id: int | None = None
    sender_name: str | None = None


class LinksResponse(BaseModel):
    query: str
    links: list[LinkItem]
    total: int
