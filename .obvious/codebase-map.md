# Codebase Map — wdm0006/todolist-mcp

Folder-level overview, depth cap 2. Single-file-per-concern layout; no sub-apps.

| Path | Kind | Purpose |
|---|---|---|
| `todo_mcp.py` | app (core) | MCP server: `Todo`/`Status`/`Priority` models, SQLite engine, 12 MCP tools (`add_item`, `list_items`, `update_item`, `mark_item_done`, `remove_item`, `get_item_by_id`, dependency tools, `assistant_workflow_guide`) |
| `kanban_web.py` | app (web) | FastAPI + HTMX kanban board over the same `todo.db` (routes `/`, `/kanban-board`, `/todos` CRUD, `/todos/{id}/details`) |
| `utc_timestamp.py` | lib | `utc_now()` UTC timestamp helper for `created_at`/`updated_at` |
| `styles.css` | asset | Standalone kanban CSS theme; not referenced by tracked Python code (the web UI embeds its own styles) |
| `tests/` | tests | 11 pytest files, 117 tests — tool functions, web UI (comprehensive/escaping/standalone), pagination, timestamps, PR workflow, dependency validation |
| `Makefile` | build | `install` / `lint` / `lint-check` / `format` / `format-check` / `test` / `clean` (uv-based) |
| `pyproject.toml` | manifest | hatchling build; deps `sqlmodel`, `fastmcp`; extras `dev` (ruff, pytest, pre-commit) and `web` (fastapi, uvicorn, jinja2, python-multipart, httpx, beautifulsoup4); ruff config |
| `.github/workflows/ci.yml` | CI | lint job + pytest matrix (3.10/3.11/3.12), uv cache |
| `.pre-commit-config.yaml` | hooks | pre-commit-hooks + ruff / ruff-format |
| `CLAUDE.md` | docs | architecture + assistant PR workflow guidance |
| `README.md` | docs | overview, install, MCP client config, tool reference, web UI usage |
| `.cursor/rules/` | docs | Cursor rule: project structure and tool reference |
| `LICENSE` | legal | MIT |
