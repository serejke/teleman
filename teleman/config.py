from __future__ import annotations

import json
from pathlib import Path

from pydantic import BaseModel
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    accounts_dir: str = "accounts"

    model_config = {"env_file": ".env", "extra": "ignore"}


class AccountConfig(BaseModel):
    model_config = {"extra": "ignore"}

    app_id: int
    app_hash: str
    phone: str


def load_account(accounts_dir: str, name: str) -> AccountConfig:
    path = Path(accounts_dir) / f"{name}.json"
    data = json.loads(path.read_text())
    return AccountConfig(**data)


def list_accounts(accounts_dir: str) -> list[str]:
    return sorted(p.stem for p in Path(accounts_dir).glob("*.json"))
