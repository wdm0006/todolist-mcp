.PHONY: lint format setup install test

setup:
	uv venv .venv

install:
	uv pip install -e .[dev]

lint:
	uv run ruff check --fix .

format:
	uv run ruff format .

test:
	uv run python -m pytest 