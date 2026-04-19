# Code Quality Rules

Non-negotiable. Every change must pass all checks before commit.

1. **No `Any` types.** Every variable, parameter, return type, and field must be concretely typed. Use Pydantic models, typed dataclasses, or union types — never `Any`, `dict[str, Any]`, or `object` as an escape hatch.
2. **No untyped dicts.** Use Pydantic `BaseModel` (or `TypedDict`) for structured data. `dict[str, X]` is fine only when X is a concrete type and the keys are genuinely dynamic.
3. **Strict mypy.** `strict = true` in pyproject.toml. Zero errors.
4. **Strict ruff.** Full rule set (see `pyproject.toml`). Zero warnings.
5. **No `# type: ignore` or `# noqa` without a comment explaining why.** If the comment can be deleted without confusing a future reader, the suppression shouldn't exist either.
6. **No bare `except:`.** Catch specific exceptions. `except Exception` only at top-level boundaries with a logged reason.
7. **No `print` in library code.** Use a logger. `T20` enforces this.
8. **Timezone-aware datetimes only.** `DTZ` enforces this.
9. **No mutable default arguments.** `B006` enforces this.
10. **Format with ruff.** `uv run ruff format` before commit. No other formatter.

## Module Layout

Code is organized TypeScript-style: one type/class per file, folders act as modules, `__init__.py` is the barrel/index that defines the public surface.

1. **One type per file.** A Pydantic model, dataclass, `TypedDict`, `Enum`, or `Protocol` gets its own file named after it in `snake_case` (`user.py` defines `User`; `order_status.py` defines `OrderStatus`). Tightly-coupled helpers for that one type may live alongside it; unrelated types do not share a file.
2. **Folders over flat files.** Prefer `models/user.py` + `models/order.py` + `models/__init__.py` over a single `models.py`. Flat files are acceptable only when a module genuinely has one type.
3. **`__init__.py` is the public API.** Each package's `__init__.py` re-exports the names that are part of its public surface (`from .user import User`). Importers use the package path (`from myapp.models import User`), never reach into submodules (`from myapp.models.user import User`) from outside the package.
4. **Domain model is isolated.** The domain package (`domain/`, `models/`, or equivalent) contains only types and pure functions — no I/O, no framework imports, no database or HTTP clients. Infrastructure depends on domain, never the reverse.
5. **Module boundaries are enforced, not conventional.** Cross-module imports go through the package's public `__init__.py`. If a type isn't re-exported there, it's private — do not import it from outside.
6. **Types live with their module, not in a global `types.py`.** Each feature/module owns its own types folder. A shared `common/` or `core/` types package exists only for genuinely cross-cutting primitives.

Boundaries above are enforced mechanically, not by review:

- **`ruff` `TID252`** — relative imports are banned; all imports are absolute.
- **`ruff` `TID251`** — per-symbol `banned-api` list in `pyproject.toml` rejects imports of private submodule paths (e.g., `myapp.models.user` when `User` is re-exported from `myapp.models`).
- **`import-linter` contracts** — architectural rules over the whole import graph: domain purity (`forbidden`), layer ordering (`layers`), feature independence (`independence`). Runs as `lint-imports` alongside `mypy` and `ruff`. Violations fail CI.

## Commands

```bash
# Run after every change:
uv run mypy teleman
uv run ruff check teleman tests/
uv run ruff format teleman tests/
uv run lint-imports
```
