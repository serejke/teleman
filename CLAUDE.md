# CLAUDE.md

## Project Overview

**teleman** is a CLI client for Telegram built with [Telethon](https://docs.telethon.dev/). Supports chatting, contact management, privacy controls, chat export, and multi-account sessions with proxy support.

## Commands

```bash
# Install dependencies
uv sync

# Run the CLI
uv run python -m teleman

# Run tests
uv run pytest

# Lint (must pass before commit)
uv run ruff check teleman/ tests/
uv run ruff format --check teleman/ tests/
```

## Code Style

- Pydantic V2 models for all data structures. Wrap Telethon responses at the boundary — never pass raw Telethon objects into application logic.
- `from __future__ import annotations` in all modules.
- Ruff for linting and formatting. Zero errors before committing.

## Architecture

- `teleman/` — main package
  - `client.py` — Telethon client wrapper, authentication, session management
  - `cli.py` — interactive CLI loop and command dispatch
  - `config.py` — app configuration
  - `models.py` — shared Pydantic models
  - `contacts.py` — contact management
  - `messages.py` — message fetching and sending
  - `privacy.py` — privacy settings management
  - `settings.py` — security/privacy summary
  - `sessions.py` — multi-account session handling
  - `proxy.py` — per-account proxy configuration
  - `report.py` — abuse reporting
  - `export/` — chat history export & sync
    - `sync.py` — forward catch-up + optional backfill; writes checkpoints
    - `models.py` — export data models (`ExportState`, `Checkpoint`, …)
    - `resolver.py` — entity resolution
    - `storage.py` — JSONL file storage (messages, checkpoints, state, meta)

## Skills

- Skills live in `.claude/skills/`. When adding or changing CLI commands, subcommands, or output shapes, update the corresponding skill's `SKILL.md` to stay in sync.

## Privacy

- Never include real chat names, usernames, user IDs, or chat IDs in files that get committed (code, skills, docs, tests). Use placeholders like `<chat>`, `12345`, `@example` in examples.

## Git Conventions

- Do not add Claude Code footer to commit messages
- Commit after each logical change (one feature / bugfix / refactor = one commit). Don't batch unrelated edits; don't leave finished work uncommitted waiting for more.
