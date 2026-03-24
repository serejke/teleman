# teleman — Vision

## Current State

Interactive CLI client for Telegram (Telethon-based). Supports chatting, contact management, privacy/security settings, session management, abuse reporting. Multi-account with proxy support.

## Direction

Extend teleman from a real-time chat client into a **Telegram data platform**: export, store, structure, and analyze chat history. The interactive CLI remains as-is. New capabilities are added as modular layers.

## Architecture Layers

### Layer 1: Export & Storage (MVP — this milestone)

- Batch export of full chat history via Telethon
- Incremental append (sync new messages since last export)
- Raw JSON storage per chat — no database
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
- Append-only — never rewrite history, only add new messages
- Type-safe boundaries — raw Telethon objects never leak past the adapter layer
