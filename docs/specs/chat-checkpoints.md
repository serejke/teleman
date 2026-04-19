# Spec: Chat Checkpoints & Sync

**Status:** draft
**Date:** 2026-04-19
**Supersedes:** `export` command (absorbed into `sync`)

## Goal

Turn teleman's one-shot chat export into a managed **sync** over tracked chats, with **per-chat checkpoint timelines**. A checkpoint is a named anchor ("forward history is caught up to here as of this moment") that future tooling (digests, analysis, LLM pipelines) can reference.

## Use cases

1. "Catch me up on all tracked chats" — `teleman sync --all` pulls new messages everywhere, appends them to each chat's messages.jsonl, writes one checkpoint per chat that had new messages.
2. "What's new in chat X since last time I looked" — a downstream tool reads `checkpoints.jsonl`, finds the previous checkpoint's `newest_id`, slices `messages.jsonl` accordingly. Teleman itself does not ship a digest command in v1; the slicing is a primitive callers implement.
3. "What was true as of April 15th" — any checkpoint id (ISO timestamp of the last message at that sync) can be referenced later to reconstruct a historical view.

## Non-goals (v1)

- **No digest command.** Building summaries / LLM prompts is explicitly out of scope. Teleman exposes the primitives (checkpoints + messages.jsonl); consumers compose their own digest pipelines.
- **No cross-chat aggregation.** Each chat has an independent checkpoint timeline. Cross-chat views are a downstream concern.
- **No global sync epochs.** We deliberately do not introduce a "sync run N across all chats" identifier; checkpoints are per-chat only.

## Domain model

### Tracked flag

Each chat has a `tracked: bool` flag stored in its `state.json`. Only tracked chats participate in batch sync.

- Default: **true** when a chat is first synced (low friction).
- `teleman sync <chat> --no-track` — initial sync without tracking (for one-off exports).
- `teleman track <chat>` / `teleman untrack <chat>` — flip the flag without syncing.
- `teleman tracked` — list all tracked chats.
- **Existing exports** (pre-migration) are auto-tracked on first run of the new code.

### Checkpoint

A checkpoint is an entry in a per-chat `checkpoints.jsonl`. It records the result of a forward-sync delta.

**File:** `data/exports/<chat_id>/checkpoints.jsonl` (append-only; one JSON object per line, newest at the bottom).

**Fields per line:**

```json
{
  "id": "2026-04-19T21:04:12+00:00", // ISO timestamp of NEWEST message in delta
  "created_at": "2026-04-19T21:10:30+00:00", // wall-clock sync time
  "newest_id": 71840, // highest message id after this sync
  "prev_newest_id": 71328, // highest message id before this sync (0 for first)
  "delta_count": 512 // newest_id - prev_newest_id, or exact count
}
```

**Invariants:**

- Checkpoint `id` is derived from the delta's newest message date — NOT wall-clock. This makes checkpoint ordering content-anchored, which is more meaningful than run-time ordering.
- Checkpoints are only created when a forward sync fetched ≥ 1 new message. Empty syncs do not create checkpoints.
- **Backfill never creates a checkpoint.** Going further back in history (`--since` with `--backfill`) is orthogonal to the forward checkpoint timeline.
- Append-only. Never rewrite. Never delete.

### Backfill streaming & resume

- During a backfill, batches of messages are appended to
  `messages.backfill.jsonl` in iteration order (newest-first) as they arrive
  — bounded memory, bounded disk I/O.
- On completion the tmp file is stream-reversed in ~64 KB blocks and
  prepended to `messages.jsonl` via an atomic rename, then deleted.
- If the process is interrupted, the tmp file is preserved. A subsequent
  `sync --backfill --since DATE` reads the oldest message from the tmp's
  tail and resumes iteration from that `offset_id` — no duplicate fetches.

### State file

`state.json` per chat gains new fields and renames:

```json
{
  "newest_id": 71840,
  "oldest_id": 1,
  "last_sync_date": "2026-04-19T21:10:30+00:00", // renamed from last_export_date
  "total_messages": 55912,
  "tracked": true // new
}
```

## CLI surface

### Replaced

- `teleman export <chat>` → **gone**. Replaced by `teleman sync <chat>`.

### New

| Command                                     | Description                                                                 |
| ------------------------------------------- | --------------------------------------------------------------------------- |
| `sync <chat>`                               | Forward catch-up for one chat. Writes checkpoint if delta > 0.              |
| `sync --all`                                | Iterate all tracked chats, continue on error, per-chat summaries in output. |
| `sync <chat> --backfill --since YYYY-MM-DD` | Forward catch-up + backward fill; only forward delta creates a checkpoint.  |
| `sync <chat> --no-track`                    | Initial sync without flipping `tracked: true`.                              |
| `track <chat>`                              | Set `tracked: true`.                                                        |
| `untrack <chat>`                            | Set `tracked: false`.                                                       |
| `tracked`                                   | List chats with `tracked: true`.                                            |
| `checkpoints <chat>`                        | Print the checkpoint history (one line per checkpoint).                     |

### Removed flags

- `--until` on export — not carried over (limited use case, re-add if needed).
- `export` verb — removed.

### Multi-account

No change. Sync operates within the currently selected `--account`, same as today. No cross-account batch.

### Rate limiting

No explicit pacing between chats during `sync --all`. Telethon's built-in flood-wait handling is sufficient for a personal tool. Revisit only if problems appear.

## Response shapes

```
sync <chat>      → {title, new_count, backfilled_count, total_messages,
                    resumed, checkpoint: {id, newest_id, delta_count} | null}
sync --all       → {results: [{chat_id, title, ...sync fields}, ...],
                    errors: [{chat_id, error}, ...]}
tracked          → {chats: [{chat_id, title, type, username, newest_id,
                              last_sync_date}, ...]}
checkpoints      → {chat_id, title, checkpoints: [{id, created_at,
                     newest_id, prev_newest_id, delta_count}, ...]}
track / untrack  → {chat_id, title, tracked: bool}
```

**Field rename:** `incremental` → `resumed` in the sync response.

## Migration from current state

1. Running `teleman sync <chat>` on an existing export:
   - Detects existing `state.json`.
   - If `tracked` field absent → set to `true` (auto-track legacy exports).
   - Performs forward catch-up; if delta > 0, creates the chat's first checkpoint.
2. `teleman tracked` on fresh install after upgrade → lists every chat under `data/exports/` (all defaulted to tracked).
3. No data migration needed for `messages.jsonl` — already chronological.

## Open questions (defer to implementation)

- Should `checkpoints <chat>` support `--json` vs default pretty output, or JSON-only like other subcommands? Current project convention is JSON-only on stdout; REPL has a separate pretty path. Follow the same.
- Where does the "resolve a checkpoint reference" helper live (for future callers using `--since last`, `--since ~2`, `--since <date>`)? Factor into a small `checkpoint_ref.py` so downstream callers outside teleman (analysis/, skills) can reuse. Not required for v1.

## Implementation sketch

### Module layout

```
teleman/export/
  exporter.py         # rename to sync.py; export_chat → sync_chat
  models.py           # ExportState gains `tracked`; add Checkpoint model
  storage.py          # add append_checkpoint, read_checkpoints, list_tracked
  checkpoints.py      # NEW: Checkpoint Pydantic model, load/append helpers
```

### Code-level changes

- `ExportState` — add `tracked: bool = True`, rename `last_export_date` → `last_sync_date`. Migrate on read (default `tracked=True` if absent).
- `Checkpoint(BaseModel)` — new model matching the file schema.
- `sync_chat()` — replaces `export_chat()`. Returns `SyncResult` that includes an optional `Checkpoint`.
- After `_catch_up_newer` returns with `count > 0`, build a `Checkpoint` and call `append_checkpoint(chat_dir, cp)`.
- `teleman/commands.py` — add `cmd_sync`, `cmd_sync_all`, `cmd_track`, `cmd_untrack`, `cmd_tracked`, `cmd_checkpoints`. Remove `cmd_export`.
- `teleman/__main__.py` — remove `export` subparser, add `sync`, `sync-all` (or merge into `sync --all`), `track`, `untrack`, `tracked`, `checkpoints`.
- `teleman/cli.py` — REPL `/sync`, `/track`, `/untrack`, `/tracked`, `/checkpoints`. Remove `/export`.
- `teleman/responses.py` — replace `ExportResponse` with `SyncResponse` + related.
- `.claude/skills/teleman/SKILL.md` — rewrite the export section.

### Tests

- `test_checkpoint_io.py` — append/read checkpoints.jsonl.
- `test_sync.py` — state-file transitions, tracked default, checkpoint creation only on non-empty delta, backfill does not create a checkpoint.
- `test_commands_sync.py` — CLI wiring.

## Phases

1. **Phase 1 (this spec)** — Checkpoints + sync + tracked flag. No digest, no cross-chat, no digest format.
2. **Phase 2 (future)** — Downstream: a separate analysis skill / tool consumes `checkpoints.jsonl` + `messages.jsonl` to produce digests. Not part of teleman.
3. **Phase 3 (future)** — Revisit: do we want `--until`? Cross-chat digest envelopes? Named checkpoint aliases? Only if real demand emerges.

## Principles this spec reinforces

- **teleman is the data layer; LLMs and summaries live outside.** Confirms vision.md layers 3 and 4.
- **JSON-first, file-per-concern storage.** Checkpoints get their own jsonl rather than being embedded in state.json, so state.json remains a compact summary while audit history grows in a separate file.
- **Append-only history for checkpoints.** Even though `messages.jsonl` can now be prepended on backfill, `checkpoints.jsonl` is strictly append-only.
