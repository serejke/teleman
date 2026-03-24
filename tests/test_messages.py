from __future__ import annotations

import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock, call

from teleman.messages import delete_all_messages, delete_dialog


def _make_raw_message(msg_id: int) -> SimpleNamespace:
    return SimpleNamespace(id=msg_id)


class TestDeleteAllMessages:
    def test_deletes_in_batches_with_revoke(self) -> None:
        ids = list(range(1, 251))
        raw_messages = [_make_raw_message(i) for i in ids]

        mock_client = AsyncMock()
        mock_client.raw.get_messages = AsyncMock(return_value=raw_messages)
        mock_client.raw.delete_messages = AsyncMock()

        count = asyncio.run(delete_all_messages(mock_client, 42))

        assert count == 250
        mock_client.raw.get_messages.assert_awaited_once_with(42, limit=None)
        assert mock_client.raw.delete_messages.await_count == 3
        calls = mock_client.raw.delete_messages.call_args_list
        assert calls[0] == call(42, ids[0:100], revoke=True)
        assert calls[1] == call(42, ids[100:200], revoke=True)
        assert calls[2] == call(42, ids[200:250], revoke=True)

    def test_no_messages_returns_zero(self) -> None:
        mock_client = AsyncMock()
        mock_client.raw.get_messages = AsyncMock(return_value=[])

        count = asyncio.run(delete_all_messages(mock_client, 42))

        assert count == 0
        mock_client.raw.delete_messages.assert_not_awaited()

    def test_single_batch(self) -> None:
        raw_messages = [_make_raw_message(i) for i in range(1, 11)]

        mock_client = AsyncMock()
        mock_client.raw.get_messages = AsyncMock(return_value=raw_messages)
        mock_client.raw.delete_messages = AsyncMock()

        count = asyncio.run(delete_all_messages(mock_client, "user123"))

        assert count == 10
        mock_client.raw.delete_messages.assert_awaited_once_with(
            "user123",
            [m.id for m in raw_messages],
            revoke=True,
        )


class TestDeleteDialog:
    def test_calls_delete_dialog(self) -> None:
        mock_client = AsyncMock()
        mock_client.raw.delete_dialog = AsyncMock()

        asyncio.run(delete_dialog(mock_client, 42))

        mock_client.raw.delete_dialog.assert_awaited_once_with(42)
