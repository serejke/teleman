from __future__ import annotations

from types import SimpleNamespace

from teleman.contacts import peer_name
from teleman.models import Group, User


class TestGroupFromTelethon:
    def test_basic_group(self) -> None:
        obj = SimpleNamespace(
            id=123,
            title="Test Group",
            username=None,
            megagroup=False,
            broadcast=False,
            gigagroup=False,
        )
        group = Group.from_telethon(obj)
        assert group.id == 123
        assert group.title == "Test Group"
        assert group.username is None
        assert group.megagroup is False
        assert group.broadcast is False
        assert group.gigagroup is False

    def test_supergroup(self) -> None:
        obj = SimpleNamespace(
            id=456,
            title="Super Group",
            username="supergroup",
            megagroup=True,
            broadcast=False,
            gigagroup=False,
        )
        group = Group.from_telethon(obj)
        assert group.id == 456
        assert group.title == "Super Group"
        assert group.username == "supergroup"
        assert group.megagroup is True

    def test_broadcast_channel(self) -> None:
        obj = SimpleNamespace(
            id=789,
            title="News Channel",
            username="news",
            megagroup=False,
            broadcast=True,
            gigagroup=False,
        )
        group = Group.from_telethon(obj)
        assert group.broadcast is True
        assert group.megagroup is False

    def test_missing_optional_attrs(self) -> None:
        obj = SimpleNamespace(id=100, title="Minimal")
        group = Group.from_telethon(obj)
        assert group.title == "Minimal"
        assert group.username is None
        assert group.megagroup is False
        assert group.broadcast is False
        assert group.gigagroup is False

    def test_none_title_becomes_empty(self) -> None:
        obj = SimpleNamespace(id=101, title=None)
        group = Group.from_telethon(obj)
        assert group.title == ""


class TestPeerName:
    def test_user_peer_name(self) -> None:
        user = User(id=1, first_name="Alice")
        assert peer_name(user) == "Alice"

    def test_group_peer_name(self) -> None:
        group = Group(id=2, title="My Group")
        assert peer_name(group) == "My Group"
