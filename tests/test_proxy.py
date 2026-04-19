from __future__ import annotations

import json
from typing import TYPE_CHECKING

import pytest

from teleman.proxy import (
    HttpProxyConfig,
    Socks4ProxyConfig,
    Socks5ProxyConfig,
    get_proxy_for_account,
    load_proxies,
)

if TYPE_CHECKING:
    from pathlib import Path


class TestHttpProxyConfig:
    def test_to_telethon_kwargs_minimal(self) -> None:
        config = HttpProxyConfig(addr="1.2.3.4", port=8080)
        result = config.to_telethon_kwargs()
        assert result == {
            "proxy": {
                "proxy_type": "http",
                "addr": "1.2.3.4",
                "port": 8080,
            }
        }

    def test_to_telethon_kwargs_with_auth(self) -> None:
        config = HttpProxyConfig(addr="1.2.3.4", port=8080, username="user", password="pass")
        result = config.to_telethon_kwargs()
        assert result == {
            "proxy": {
                "proxy_type": "http",
                "addr": "1.2.3.4",
                "port": 8080,
                "username": "user",
                "password": "pass",
            }
        }


class TestSocks5ProxyConfig:
    def test_to_telethon_kwargs_minimal(self) -> None:
        config = Socks5ProxyConfig(addr="1.2.3.4", port=1080)
        result = config.to_telethon_kwargs()
        assert result == {
            "proxy": {
                "proxy_type": "socks5",
                "addr": "1.2.3.4",
                "port": 1080,
                "rdns": True,
            }
        }

    def test_to_telethon_kwargs_with_auth(self) -> None:
        config = Socks5ProxyConfig(
            addr="1.2.3.4", port=1080, username="u", password="p", rdns=False
        )
        result = config.to_telethon_kwargs()
        assert result == {
            "proxy": {
                "proxy_type": "socks5",
                "addr": "1.2.3.4",
                "port": 1080,
                "rdns": False,
                "username": "u",
                "password": "p",
            }
        }


class TestSocks4ProxyConfig:
    def test_to_telethon_kwargs_minimal(self) -> None:
        config = Socks4ProxyConfig(addr="1.2.3.4", port=1080)
        result = config.to_telethon_kwargs()
        assert result == {
            "proxy": {
                "proxy_type": "socks4",
                "addr": "1.2.3.4",
                "port": 1080,
                "rdns": True,
            }
        }

    def test_to_telethon_kwargs_with_auth(self) -> None:
        config = Socks4ProxyConfig(
            addr="1.2.3.4", port=1080, username="u", password="p", rdns=False
        )
        result = config.to_telethon_kwargs()
        assert result == {
            "proxy": {
                "proxy_type": "socks4",
                "addr": "1.2.3.4",
                "port": 1080,
                "rdns": False,
                "username": "u",
                "password": "p",
            }
        }


class TestLoadProxies:
    def test_load_proxies_from_json(self, tmp_path: Path) -> None:
        data = {
            "account1": {
                "type": "http",
                "addr": "proxy.example.com",
                "port": 8080,
                "username": "user",
                "password": "pass",
            },
            "account2": {
                "type": "socks5",
                "addr": "socks.example.com",
                "port": 1080,
            },
        }
        (tmp_path / "proxies.json").write_text(json.dumps(data))

        proxies = load_proxies(str(tmp_path))
        assert len(proxies) == 2
        assert isinstance(proxies["account1"], HttpProxyConfig)
        assert proxies["account1"].addr == "proxy.example.com"
        assert proxies["account1"].username == "user"
        assert isinstance(proxies["account2"], Socks5ProxyConfig)
        assert proxies["account2"].port == 1080

    def test_load_proxies_with_null(self, tmp_path: Path) -> None:
        data = {
            "account1": {
                "type": "http",
                "addr": "proxy.example.com",
                "port": 8080,
            },
            "account2": None,
        }
        (tmp_path / "proxies.json").write_text(json.dumps(data))

        proxies = load_proxies(str(tmp_path))
        assert len(proxies) == 2
        assert isinstance(proxies["account1"], HttpProxyConfig)
        assert proxies["account2"] is None

    def test_load_proxies_missing_file(self, tmp_path: Path) -> None:
        proxies = load_proxies(str(tmp_path))
        assert proxies == {}

    def test_load_proxies_invalid_type(self, tmp_path: Path) -> None:
        data = {
            "account1": {
                "type": "invalid",
                "addr": "1.2.3.4",
                "port": 8080,
            }
        }
        (tmp_path / "proxies.json").write_text(json.dumps(data))

        with pytest.raises(ValueError, match="invalid"):
            load_proxies(str(tmp_path))


class TestGetProxyForAccount:
    def test_found(self) -> None:
        config = HttpProxyConfig(addr="1.2.3.4", port=8080)
        proxies: dict[str, HttpProxyConfig | None] = {"myaccount": config}
        result = get_proxy_for_account(proxies, "myaccount")
        assert result is config

    def test_null_means_direct(self) -> None:
        proxies: dict[str, HttpProxyConfig | None] = {"myaccount": None}
        result = get_proxy_for_account(proxies, "myaccount")
        assert result is None

    def test_missing_raises(self) -> None:
        config = HttpProxyConfig(addr="1.2.3.4", port=8080)
        proxies: dict[str, HttpProxyConfig | None] = {"other": config}
        with pytest.raises(KeyError, match="myaccount"):
            get_proxy_for_account(proxies, "myaccount")
