# todolist-mcp — Agent Guide

**Repo:** `wdm0006/todolist-mcp` (default branch `main`) — an MCP server for a SQLite-backed todo list, plus an optional FastAPI + HTMX kanban web UI over the same database.

## Stack

| Layer | Technology |
|---|---|
| Language | Python >= 3.10 (CI matrix 3.10/3.11/3.12; onboarding sandbox ran 3.13.14) |
| Package manager | `uv` (not preinstalled on a fresh sandbox — see `skills/local-dev/SKILL.md`) |
| Core app | MCP server: `todo_mcp.py`, FastMCP 2.x, stdio transport |
| Database | SQLite via SQLModel/SQLAlchemy — single `todo.db` file inside `--project-dir` |
| Web UI | `kanban_web.py`: FastAPI + uvicorn + Jinja2 + HTMX |
| Tests | pytest — 11 files in `tests/`, 117 tests |
| Lint / format | ruff (target py310, line length 120, double quotes) |
| Hooks | pre-commit (ruff, ruff-format, whitespace/yaml/large-file checks) |
| CI | `.github/workflows/ci.yml` — `lint` job + `test` matrix (Python 3.10/3.11/3.12) |

No external services (no Postgres/Redis), no required env vars, no secrets. All state lives in a SQLite file.

## Apps

### 1. MCP server (core) — `todo_mcp.py`

Stdio MCP server; requires an **existing** directory passed as `--project-dir` (it exits with an error if the path does not exist). Database: `<project-dir>/todo.db`, created automatically on first run — no migrate/seed step.

MCP tools (wire names are underscore-form; the hyphenated names in README/CLAUDE.md are display aliases):

`add_item`, `list_items`, `update_item`, `mark_item_done`, `remove_item`, `get_item_by_id`, `add_dependency`, `remove_dependency`, `list_dependencies`, `get_ready_items`, `get_dependency_chain`, `assistant_workflow_guide`

### 2. Kanban web UI — `kanban_web.py`

| Route | Purpose |
|---|---|
| `GET /` | Kanban board page |
| `GET /kanban-board` | Board fragment for HTMX refresh |
| `POST /todos` | Create — form fields `description`, `priority`, `tags`, `due_date`, `long_description` -> 303 |
| `PUT /todos/{id}/status` | Change status — form field `status` -> JSON `{"success": true}` |
| `DELETE /todos/{id}` | Delete -> 303 |
| `GET /todos/{id}/details` | Item details fragment |

Default listen address `http://127.0.0.1:8000`; override with `--host` / `--port`. Without `--project-dir` it uses `./todo.db` in the cwd.

Both entry scripts are self-contained uv scripts (`# /// script` dependency blocks) — `uv run <script>.py` works without installing the package.

## Commands

| Task | Command |
|---|---|
| Install (creates `.venv`, installs `.[dev,web]`) | `make install` |
| Lint (auto-fix) | `make lint` |
| Lint (check only) | `make lint-check` |
| Format | `make format` |
| Format (check only) | `make format-check` |
| Tests | `make test` |
| Start MCP server | `uv run todo_mcp.py --project-dir <dir>` |
| Start web UI | `uv run kanban_web.py --project-dir <dir>` |
| Clean | `make clean` |

## Local Verification Summary (onboarding run 2026-09-06)

- `make install` (uv venv + `uv pip install -e ".[dev,web]"`) — OK
- `uv run pytest tests/` — **117 passed** (4 deprecation warnings)
- `uv run ruff check .` — all checks passed
- `uv run ruff format --check .` — 14 files already formatted
- Web UI on `127.0.0.1:8000`; full CRUD exercised over HTTP: `POST /todos` -> 303, item present in `GET /`, `PUT /todos/1/status` -> `{"success":true}`, `GET /todos/1/details` -> 200, `DELETE /todos/1` -> 303, item gone afterwards
- MCP flow exercised over stdio with a fastmcp `Client`: 12 tools listed; `add_item` -> item created (priority high, tags, due date); `list_items` -> 1 item; `mark_item_done` -> status `done`; `remove_item` -> removed
- Playwright headless-chromium screenshot of the board (`/tmp/kanban_screenshot.png` in the snapshot): title "Todo Kanban Board", cards rendered, **no console or page errors**
- `todo.db` created automatically — no manual migration or seeding

## Codebase map

See [codebase-map.md](codebase-map.md).

## Sandbox snapshot

- Snapshot ID (e2b template): `v54w0was8co0b6wz9zz0:default`
- Built at: `2026-09-06T20:28:49.561Z`
- Captured from the live session with the web UI running on `127.0.0.1:8000` and the venv installed

## Guidance docs

`README.md` (tool reference + web UI usage), `CLAUDE.md` (architecture + assistant PR workflow), `.cursor/rules/todo-list-mcp-overview.mdc`, `.pre-commit-config.yaml`.
