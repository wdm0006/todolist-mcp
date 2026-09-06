---
name: local-dev
description: Bring up and verify the todolist-mcp dev stack — uv setup, MCP stdio server, kanban web UI on 127.0.0.1:8000, tests and lint
---

# local-dev — todolist-mcp onboarding record

Recorded from a successful onboarding run on 2026-09-06 (sandbox `cmp_RigydVyc`). Everything below was executed and verified in that session.

## 1. Install uv (fresh sandbox only)

`uv` is NOT preinstalled. Install once per sandbox:

```bash
curl -LsSf https://astral.sh/uv/install.sh -o /tmp/uv-install.sh && sh /tmp/uv-install.sh
export PATH="$HOME/.local/bin:$PATH"
```

System python (3.13) satisfies `requires-python >= 3.10`.

## 2. Install dependencies

```bash
make install    # uv venv .venv --seed; uv pip install -e ".[dev,web]"
```

~30s. `.venv/` and `uv.lock` are gitignored.

## 3. Start the kanban web UI (primary web flow)

```bash
mkdir -p /tmp/todolist-dev
setsid nohup uv run kanban_web.py --project-dir /tmp/todolist-dev --host 127.0.0.1 --port 8000 > /tmp/kanban.log 2>&1 &
```

- Parse the real address from the log line: `Uvicorn running on http://127.0.0.1:8000`.
- Fully detach the process (`setsid` + redirect) — a bare `&` keeps the shell call open until it times out.
- `uv run` on the entry scripts builds a separate cached uv env from the embedded `# /// script` deps; that is expected.

Health check: `curl -s -o /dev/null -w "%{http_code}" http://127.0.0.1:8000/` -> `200`.

CRUD smoke (form-encoded): `POST /todos` (fields `description`, `priority`, `tags`, `due_date`) -> 303; `PUT /todos/{id}/status` (`status`) -> `{"success":true}`; `DELETE /todos/{id}` -> 303; `GET /todos/{id}/details` -> 200.

## 4. Verify the MCP server (primary MCP flow)

`--project-dir` must point at an existing directory or the server exits immediately.

```python
# run with .venv/bin/python from the repo root
from fastmcp import Client
from fastmcp.client.transports import StdioTransport

transport = StdioTransport(".venv/bin/python", ["todo_mcp.py", "--project-dir", "/tmp/todolist-mcp-dev"])
async with Client(transport) as client:
    tools = await client.list_tools()            # 12 tools
    r = await client.call_tool("add_item", {"description": "smoke", "priority": "high"})
```

Gotcha: wire tool names are `add_item` / `list_items` / `mark_item_done` / `remove_item` (underscores). The hyphenated `add-item` forms from README/CLAUDE.md fail with `Unknown tool`.

## 5. Tests and lint

```bash
uv run pytest tests/            # 117 passed
uv run ruff check .             # all checks passed
uv run ruff format --check .    # 14 files already formatted
```

## 6. Screenshot (optional evidence)

Playwright is not preinstalled; `pip install playwright && python3 -m playwright install chromium --with-deps` (~115 MB) worked. The board renders with title "Todo Kanban Board" and no console errors.

## Facts confirmed on this stack

- No external services; SQLite file `todo.db` auto-created in the project dir — no migrate/seed step.
- No env vars, no secrets required.
- Only the web UI listens on a port (default 8000); the MCP server is stdio-only.
- CI (GitHub Actions) runs the same ruff + pytest commands on Python 3.10/3.11/3.12.
