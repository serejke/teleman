from __future__ import annotations

import json
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Annotated, Any, Literal

from pydantic import BaseModel, Field, TypeAdapter

PROXIES_FILENAME = "proxies.json"


class BaseProxyConfig(BaseModel, ABC):
    addr: str
    port: int
    username: str | None = None
    password: str | None = None

    @abstractmethod
    def to_telethon_kwargs(self) -> dict[str, Any]: ...


class HttpProxyConfig(BaseProxyConfig):
    type: Literal["http"] = "http"

    def to_telethon_kwargs(self) -> dict[str, Any]:
        proxy: dict[str, Any] = {
            "proxy_type": "http",
            "addr": self.addr,
            "port": self.port,
        }
        if self.username is not None:
            proxy["username"] = self.username
        if self.password is not None:
            proxy["password"] = self.password
        return {"proxy": proxy}


class Socks5ProxyConfig(BaseProxyConfig):
    type: Literal["socks5"] = "socks5"
    rdns: bool = True

    def to_telethon_kwargs(self) -> dict[str, Any]:
        proxy: dict[str, Any] = {
            "proxy_type": "socks5",
            "addr": self.addr,
            "port": self.port,
            "rdns": self.rdns,
        }
        if self.username is not None:
            proxy["username"] = self.username
        if self.password is not None:
            proxy["password"] = self.password
        return {"proxy": proxy}


class Socks4ProxyConfig(BaseProxyConfig):
    type: Literal["socks4"] = "socks4"
    rdns: bool = True

    def to_telethon_kwargs(self) -> dict[str, Any]:
        proxy: dict[str, Any] = {
            "proxy_type": "socks4",
            "addr": self.addr,
            "port": self.port,
            "rdns": self.rdns,
        }
        if self.username is not None:
            proxy["username"] = self.username
        if self.password is not None:
            proxy["password"] = self.password
        return {"proxy": proxy}


ProxyConfig = Annotated[
    HttpProxyConfig | Socks5ProxyConfig | Socks4ProxyConfig,
    Field(discriminator="type"),
]


def load_proxies(accounts_dir: str) -> dict[str, ProxyConfig | None]:
    path = Path(accounts_dir) / PROXIES_FILENAME
    if not path.exists():
        return {}
    data = json.loads(path.read_text())
    adapter = TypeAdapter(dict[str, ProxyConfig | None])
    return adapter.validate_python(data)


def get_proxy_for_account(proxies: dict[str, ProxyConfig | None], name: str) -> ProxyConfig | None:
    if name not in proxies:
        raise KeyError(
            f"Account {name!r} not found in {PROXIES_FILENAME}. "
            f"Add it with a proxy config or null for direct connection."
        )
    return proxies.get(name)
