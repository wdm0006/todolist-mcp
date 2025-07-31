.PHONY: lint format setup install test

setup:
	uv venv .venv

install:
	uv pip install -e .[dev]

install-ui:
	uv pip install -e .[dev,ui]

lint:
	uv run ruff check --fix .

format:
	uv run ruff format .

test:
	uv run python -m pytest 