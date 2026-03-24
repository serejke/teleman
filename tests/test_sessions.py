from __future__ import annotations

import asyncio
from datetime import UTC, datetime
from types import SimpleNamespace
from unittest.mock import AsyncMock

from teleman.sessions import Session, end_session, get_sessions


def _make_raw_auth(
    *,
    hash: int = 123,
    current: bool = False,
    device_model: str = "iPhone 15",
    platform: str = "iOS",
    system_version: str = "17.0",
    app_name: str = "Telegram iOS",
    app_version: str = "10.0",
    ip: str = "1.2.3.4",
    country: str = "US",
    date_created: datetime | None = None,
    date_active: datetime | None = None,
    official_app: bool = True,
) -> SimpleNamespace:
    now = datetime.now(tz=UTC)
    return SimpleNamespace(
        hash=hash,
        current=current,
        device_model=device_model,
        platform=platform,
        system_version=system_version,
        app_name=app_name,
        app_version=app_version,
        ip=ip,
        country=country,
        date_created=date_created or now,
        date_active=date_active or now,
        official_app=official_app,
    )


class TestSessionFromTelethon:
    def test_basic_fields(self) -> None:
        raw = _make_raw_auth(hash=42, current=True, device_model="Pixel 8", ip="5.6.7.8")
        session = Session.from_telethon(raw)
        assert session.hash == 42
        assert session.current is True
        assert session.device_model == "Pixel 8"
        assert session.ip == "5.6.7.8"

    def test_none_fields_default_to_empty(self) -> None:
        raw = _make_raw_auth()
        raw.device_model = None
        raw.platform = None
        raw.ip = None
        raw.country = None
        raw.official_app = None
        raw.current = None
        session = Session.from_telethon(raw)
        assert session.device_model == ""
        assert session.platform == ""
        assert session.ip == ""
        assert session.country == ""
        assert session.official_app is False
        assert session.current is False


class TestGetSessions:
    def test_returns_sessions(self) -> None:
        raw_auths = [_make_raw_auth(hash=1, current=True), _make_raw_auth(hash=2)]
        mock_client = AsyncMock()
        mock_client.raw = AsyncMock(return_value=SimpleNamespace(authorizations=raw_auths))

        sessions = asyncio.run(get_sessions(mock_client))
        assert len(sessions) == 2
        assert sessions[0].hash == 1
        assert sessions[0].current is True
        assert sessions[1].hash == 2
        assert sessions[1].current is False


class TestEndSession:
    def test_returns_result(self) -> None:
        mock_client = AsyncMock()
        mock_client.raw = AsyncMock(return_value=True)

        result = asyncio.run(end_session(mock_client, 42))
        assert result is True
