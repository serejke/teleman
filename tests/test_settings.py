from __future__ import annotations

import asyncio
from datetime import UTC, datetime
from types import SimpleNamespace
from unittest.mock import AsyncMock

from teleman.settings import (
    AccountTTL,
    TwoFactorStatus,
    WebSession,
    end_all_web_sessions,
    end_web_session,
    get_2fa_status,
    get_account_ttl,
    get_web_sessions,
    set_account_ttl,
)


class TestTwoFactorStatus:
    def test_from_telethon_enabled(self) -> None:
        raw = SimpleNamespace(has_password=True, has_recovery=True, email_unconfirmed_pattern=None)
        status = TwoFactorStatus.from_telethon(raw)
        assert status.enabled is True
        assert status.has_recovery_email is True

    def test_from_telethon_disabled(self) -> None:
        raw = SimpleNamespace(
            has_password=False, has_recovery=False, email_unconfirmed_pattern=None
        )
        status = TwoFactorStatus.from_telethon(raw)
        assert status.enabled is False
        assert status.has_recovery_email is False

    def test_from_telethon_unconfirmed_email(self) -> None:
        raw = SimpleNamespace(
            has_password=True, has_recovery=False, email_unconfirmed_pattern="t***@example.com"
        )
        status = TwoFactorStatus.from_telethon(raw)
        assert status.enabled is True
        assert status.has_recovery_email is True

    def test_get_2fa_status(self) -> None:
        raw = SimpleNamespace(has_password=True, has_recovery=True, email_unconfirmed_pattern=None)
        mock_client = AsyncMock()
        mock_client.raw = AsyncMock(return_value=raw)

        status = asyncio.run(get_2fa_status(mock_client))
        assert status.enabled is True
        assert status.has_recovery_email is True


class TestAccountTTL:
    def test_from_telethon(self) -> None:
        raw = SimpleNamespace(days=365)
        ttl = AccountTTL.from_telethon(raw)
        assert ttl.days == 365

    def test_get_account_ttl(self) -> None:
        raw = SimpleNamespace(days=180)
        mock_client = AsyncMock()
        mock_client.raw = AsyncMock(return_value=raw)

        ttl = asyncio.run(get_account_ttl(mock_client))
        assert ttl.days == 180

    def test_set_account_ttl(self) -> None:
        mock_client = AsyncMock()
        # First call: SetAccountTTLRequest returns True
        # Second call: GetAccountTTLRequest returns the new TTL
        mock_client.raw = AsyncMock(side_effect=[True, SimpleNamespace(days=90)])

        ttl = asyncio.run(set_account_ttl(mock_client, 90))
        assert ttl.days == 90


class TestWebSession:
    def test_from_telethon(self) -> None:
        now = datetime.now(tz=UTC)
        raw = SimpleNamespace(
            hash=999,
            domain="example.com",
            browser="Chrome",
            platform="Windows",
            ip="10.0.0.1",
            region="US",
            date_created=now,
            date_active=now,
            bot_name="TestBot",
        )
        ws = WebSession.from_telethon(raw)
        assert ws.hash == 999
        assert ws.domain == "example.com"
        assert ws.browser == "Chrome"
        assert ws.bot_name == "TestBot"

    def test_from_telethon_none_fields(self) -> None:
        now = datetime.now(tz=UTC)
        raw = SimpleNamespace(
            hash=1,
            domain=None,
            browser=None,
            platform=None,
            ip=None,
            region=None,
            date_created=now,
            date_active=now,
        )
        ws = WebSession.from_telethon(raw)
        assert ws.domain == ""
        assert ws.browser == ""
        assert ws.bot_name == ""

    def test_get_web_sessions(self) -> None:
        now = datetime.now(tz=UTC)
        raw_auths = [
            SimpleNamespace(
                hash=1,
                domain="a.com",
                browser="Firefox",
                platform="Linux",
                ip="1.1.1.1",
                region="DE",
                date_created=now,
                date_active=now,
                bot_name="Bot1",
            ),
            SimpleNamespace(
                hash=2,
                domain="b.com",
                browser="Safari",
                platform="macOS",
                ip="2.2.2.2",
                region="UK",
                date_created=now,
                date_active=now,
                bot_name="Bot2",
            ),
        ]
        mock_client = AsyncMock()
        mock_client.raw = AsyncMock(return_value=SimpleNamespace(authorizations=raw_auths))

        sessions = asyncio.run(get_web_sessions(mock_client))
        assert len(sessions) == 2
        assert sessions[0].domain == "a.com"
        assert sessions[1].hash == 2

    def test_end_web_session(self) -> None:
        mock_client = AsyncMock()
        mock_client.raw = AsyncMock(return_value=True)

        result = asyncio.run(end_web_session(mock_client, 42))
        assert result is True

    def test_end_all_web_sessions(self) -> None:
        mock_client = AsyncMock()
        mock_client.raw = AsyncMock(return_value=True)

        result = asyncio.run(end_all_web_sessions(mock_client))
        assert result is True
