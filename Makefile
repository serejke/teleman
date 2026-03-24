.PHONY: install run repl test lint format check

install:
	uv sync

run:
	uv run python -m teleman

repl:
	uv run python -m teleman repl

test:
	uv run pytest

lint:
	uv run ruff check teleman/ tests/

format:
	uv run ruff format teleman/ tests/

check: lint
	uv run ruff format --check teleman/ tests/
