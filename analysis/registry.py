"""Auto-discovers analysis skill modules (analysis/stats_*.py).

Each skill module must export:
    NAME: str           — short identifier (e.g. "overview")
    DESCRIPTION: str    — one-line summary for --list
    compute(messages: list[Message]) -> BaseModel   — deterministic, typed output
"""

from __future__ import annotations

import importlib
import pkgutil
from types import ModuleType

from pydantic import BaseModel

import analysis
from analysis.loader import Message


def _discover() -> dict[str, ModuleType]:
    skills: dict[str, ModuleType] = {}
    for info in pkgutil.iter_modules(analysis.__path__, analysis.__name__ + "."):
        if not info.name.split(".")[-1].startswith("stats_"):
            continue
        mod = importlib.import_module(info.name)
        name = getattr(mod, "NAME", None)
        if name and hasattr(mod, "compute"):
            skills[name] = mod
    return skills


_cache: dict[str, ModuleType] | None = None


def get_skills() -> dict[str, ModuleType]:
    global _cache
    if _cache is None:
        _cache = _discover()
    return _cache


class SkillInfo(BaseModel):
    name: str
    description: str


def list_skills() -> list[SkillInfo]:
    return [SkillInfo(name=mod.NAME, description=getattr(mod, "DESCRIPTION", "")) for mod in get_skills().values()]


def run_skill(name: str, messages: list[Message]) -> BaseModel:
    skills = get_skills()
    if name not in skills:
        raise KeyError(f"Unknown skill: {name!r}. Available: {sorted(skills)}")
    return skills[name].compute(messages)
