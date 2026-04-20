# teleman — Vision

## Current State

Interactive CLI client for Telegram (Telethon-based). Supports chatting, contact management, privacy/security settings, session management, abuse reporting. Multi-account with proxy support.

## Direction

Extend teleman from a real-time chat client into a **Telegram data platform**: sync, store, structure, and analyze chat history. The interactive CLI remains as-is. New capabilities are added as modular layers.

## Architecture Layers

### Layer 1: Sync & Storage (MVP — this milestone)

- Checkpointed chat sync via Telethon: forward catch-up on new messages + backward fill of older history (bounded by `--since` / `--until`)
- Raw JSON storage per chat, kept chronological on disk — no database
- Per-chat `tracked` flag + append-only `checkpoints.jsonl` for managed sync
- Batch `sync --all` across every tracked chat
- Configurable download directory (project-local, gitignored)

### Layer 2: Structuring (future)

- Thread reconstruction from reply chains
- Conversation grouping
- Entity extraction (links, files, media) into separate indices

### Layer 3: LLM Processing (future)

- Pluggable processing pipeline on raw data
- Embeddings + vector search (RAG)
- LLM pre-summarization of threads
- Modular — swap approaches without changing storage

### Layer 4: Query Interface (future)

- CLI or programmatic API for querying indexed data
- Natural language queries over chat history

## Tech Stack

- Python 3.13, Telethon, Pydantic V2
- Strict: mypy, ruff, enforced type checking
- Docker for e2e tests
- uv for package management

## Principles

- JSON-first storage — no database until proven necessary
- Modular layers — each layer works independently
- Chronological storage with dual growth — `messages.jsonl` may be appended (new messages) or prepended (backfilled older messages) via atomic rewrites. `checkpoints.jsonl` is strictly append-only.
- Type-safe boundaries — raw Telethon objects never leak past the adapter layer
