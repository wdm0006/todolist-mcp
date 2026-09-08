# Todolist MCP

A Model Context Protocol (MCP) server for managing a todo list backed by SQLite. Enables AI assistants to interact with a persistent, queryable todo list for project management and task tracking.

## Features

The server provides the following tools:

- **`add-item`**: Add a new todo item with description, long description, priority, due date, and tags.
- **`get-item-by-id`**: Retrieve a single todo item by its ID.
- **`list-items`**: List todo items, with optional filters for status, priority, and tags, sorting, and `limit`/`offset` pagination.
- **`update-item`**: Update fields of an existing todo item (description, long description, status, priority, due date, tags).
- **`mark-item-done`**: Mark a todo item as done.
- **`remove-item`**: Remove a todo item from the database.
- **`add-dependency`**: Declare that one todo item blocks another (blocker → blocked).
- **`remove-dependency`**: Remove an existing blocker → blocked dependency.
- **`list-dependencies`**: List dependencies for one item (what blocks it, what it blocks) or all dependencies.
- **`get-ready-items`**: Get open items that are ready to work on — not blocked, or whose blockers are all done/cancelled.
- **`get-dependency-chain`**: Traverse an item's full upstream/downstream dependency chain (with cycle detection on writes).
- **`assistant-workflow-guide`**: Get a comprehensive workflow guide for code assistants.

## Install

```bash
# Run directly from GitHub (no install needed)
uvx --from git+https://github.com/wdm0006/todolist-mcp todolist-mcp --project-dir /path/to/your/project

# Or install from source
git clone https://github.com/wdm0006/todolist-mcp
cd todolist-mcp
uv sync
uv run todo_mcp.py --project-dir /path/to/your/project
```

## MCP Client Configuration

```json
{
  "mcpServers": {
    "todolist": {
      "command": "uvx",
      "args": [
        "--from", "git+https://github.com/wdm0006/todolist-mcp",
        "todolist-mcp",
        "--project-dir", "/path/to/your/project"
      ]
    }
  }
}
```

## Usage Examples

You can connect any MCP client (like Claude.ai, Windsurf, or Cursor) to these servers. Example prompts for an AI assistant:

### Todo List Examples

**Adding a Todo:**
- "Add a todo: 'Buy groceries', priority high, due tomorrow, tags: shopping,errands." (Calls `add-item`)

**Listing Todos:**
- "Show all open todos sorted by due date." (Calls `list-items` with filters)
- "List all todos with the tag 'work' and priority high." (Calls `list-items` with tag and priority filters)

**Updating Todos:**
- "Update todo #3: set status to in_progress and priority to low." (Calls `update-item`)

**Marking as Done:**
- "Mark todo #5 as done." (Calls `mark-item-done`)

**Planning with Dependencies:**
- "Make todo #7 blocked until todo #3 is finished." (Calls `add-dependency` with #3 as the blocker)
- "What can I work on right now?" (Calls `get-ready-items`)
- "What is standing in the way of todo #7?" (Calls `list-dependencies` or `get-dependency-chain`)

**Removing a Todo:**
- "Remove todo #2." (Calls `remove-item`)

**Getting Help:**
- "How should I use this todo system for project management?" (Calls `assistant-workflow-guide`)

## Web Interface

A modern FastAPI + HTMX kanban board interface is provided for human users to visualize and manage the same todo database that AI assistants use.

### Running the Kanban Web UI

The web interface is a self-contained script with embedded dependencies:

```bash
# Run directly with uv (recommended)
uv run kanban_web.py --project-dir /path/to/your/project

# Or install web dependencies and run with Python
pip install -e .[web]
python kanban_web.py --project-dir /path/to/your/project
```

The interface will be available at `http://127.0.0.1:8000`

### Example Usage

```bash
# Run the kanban interface for a specific project
uv run kanban_web.py --project-dir /Users/yourname/projects/my-app

# Use the same project directory as your MCP server
uv run kanban_web.py --project-dir /path/to/project

# Custom host and port
uv run kanban_web.py --project-dir /path/to/project --host 0.0.0.0 --port 3000
```

### Features

- **🚀 Modern Tech Stack**: FastAPI + HTMX for dynamic updates without full page reloads
- **🎨 Retro Hacker Theme**: Cyberpunk aesthetic with neon colors, terminal fonts, and glowing effects
- **📋 Drag & Drop Kanban**: Visual swimlanes with smooth drag-and-drop between statuses
- **🏷️ Smart Tags**: Colorful, bracketed tags with category-specific styling
- **✏️ Modal Forms**: Beautiful create/edit modals with terminal-style inputs
- **⚡ Priority System**: Glowing priority indicators with color coding
- **🔄 Real-time Updates**: HTMX-powered dynamic updates for seamless interaction
- **🗑️ Safe Operations**: Delete confirmations and proper error handling
- **📱 Responsive Design**: Works on desktop, tablet, and mobile devices
- **⚙️ Single File**: Self-contained with embedded dependencies using uv script format
- **🎯 No JavaScript Build**: Pure HTML/CSS/JS with CDN dependencies

This provides a perfect complement to AI assistant management - assistants can work programmatically via MCP tools while humans get visual oversight and control through a beautiful, modern web interface.

## Tool Reference

All tools take snake_case parameter names over MCP (the hyphenated names above are display aliases). Every tool returns a dictionary — either the requested data, or `{"error": "message"}` on invalid input.

---

**`add-item`**

- **Description**: Add a new todo item.
- **Parameters**:
    - `description` (`str`): Description of the todo item.
    - `long_description` (`str`, optional): Extended details — acceptance criteria, notes, links. Rendered in the kanban details view.
    - `priority` (`str`, optional): One of `'high'`, `'medium'`, `'low'`. Default: `'medium'`.
    - `due_date_str` (`str`, optional): Due date in `YYYY-MM-DD` format.
    - `tags` (`str`, optional): Comma-separated tags, e.g. `"backend,security"`.
- **Returns**: The created todo item as a dictionary, or an error message.

---

**`get-item-by-id`**

- **Description**: Retrieve a single todo item by its ID.
- **Parameters**:
    - `item_id` (`int`): ID of the todo item.
- **Returns**: The todo item as a dictionary, or an error message if not found.

---

**`list-items`**

- **Description**: List todo items with optional filters, sorting, and pagination.
- **Parameters**:
    - `show_all_statuses` (`bool`, optional): If `True`, show all statuses. Default: `False` (open and in_progress only).
    - `status_filter` (`str` or `list[str]`, optional): Filter by status (`'open'`, `'in_progress'`, `'done'`, `'cancelled'`). A list matches any of the statuses.
    - `priority_filter` (`str` or `list[str]`, optional): Filter by priority (`'high'`, `'medium'`, `'low'`). A list matches any of the priorities.
    - `sort_by` (`str`, optional): Field to sort by (`'priority'`, `'due_date'`, `'created_at'`, `'status'`, `'description'`, `'id'`). Prefix with `-` for descending (e.g. `'-created_at'`). Under `due_date`, undated items sort last in both directions.
    - `tag_filter` (`str` or `list[str]`, optional): Filter by tag. Tags match **exactly, case-insensitively** — this is not a substring search. Multiple tags combine with AND: `["work", "urgent"]` returns only items carrying both tags. Tag lists on items are comma-separated.
    - `limit` (`int`, optional): Maximum number of items to return. Must be non-negative (`0` returns an empty page).
    - `offset` (`int`, optional): Number of items to skip before the first returned. Must be non-negative.
- **Returns**: `{"items": [list_of_items]}`, or `{"items": [...], "total_count": int}` when `limit` and/or `offset` are used — `total_count` is the number of matching items **before** pagination is applied, so clients can page through the full result set.

---

**`update-item`**

- **Description**: Update fields of an existing todo item. Only provided fields are changed.
- **Parameters**:
    - `item_id` (`int`): ID of the todo item.
    - `description` (`str`, optional): New description.
    - `long_description` (`str`, optional): New extended details.
    - `status` (`str`, optional): New status (`'open'`, `'in_progress'`, `'done'`, `'cancelled'`).
    - `priority` (`str`, optional): New priority (`'high'`, `'medium'`, `'low'`).
    - `due_date_str` (`str`, optional): New due date (`YYYY-MM-DD`) or `'none'` to clear.
    - `tags` (`str`, optional): New tags (comma-separated) or `'none'` to clear.
- **Returns**: The updated todo item as a dictionary, or an error/message.

---

**`mark-item-done`**

- **Description**: Mark a todo item as done.
- **Parameters**:
    - `item_id` (`int`): ID of the todo item.
- **Returns**: The updated todo item as a dictionary, or an error message.

---

**`remove-item`**

- **Description**: Remove a todo item from the database.
- **Parameters**:
    - `item_id` (`int`): ID of the todo item.
- **Returns**: Message and ID of the removed item, or an error message.

---

**`add-dependency`**

- **Description**: Declare that one todo item blocks another. Writes are validated: both items must exist, the edge must not already exist, and adding the edge must not create a cycle.
- **Parameters**:
    - `blocker_id` (`int`): ID of the todo item that blocks another.
    - `blocked_id` (`int`): ID of the todo item that is blocked.
- **Returns**: `{"message": ..., "dependency": {...}}` with both endpoints, or an error message (self-dependency, missing item, duplicate edge, or cycle).

---

**`remove-dependency`**

- **Description**: Remove an existing blocker → blocked dependency.
- **Parameters**:
    - `blocker_id` (`int`): ID of the blocking item.
    - `blocked_id` (`int`): ID of the blocked item.
- **Returns**: `{"message": ..., "status": "removed"}`, or an error message if no such dependency exists.

---

**`list-dependencies`**

- **Description**: List dependencies for one todo item, or all dependencies in the database.
- **Parameters**:
    - `item_id` (`int`, optional): ID of the item to inspect. Omit to list every dependency.
- **Returns**: With `item_id`: `{"item": {...}, "blocked_by": [items blocking it], "blocks": [items it blocks]}`. Without: `{"dependencies": [{id, blocker, blocked, created_at}, ...]}`.

---

**`get-ready-items`**

- **Description**: Get open/in-progress items that are ready to work on — not blocked, or whose blockers are all done/cancelled.
- **Parameters**: None.
- **Returns**: `{"ready": [items sorted by priority then due date], "blocked": [items each with a `blocked_by` list], "summary": {"ready_count": int, "blocked_count": int}}`.

---

**`get-dependency-chain`**

- **Description**: Traverse an item's full dependency chain in either direction, following blocker → blocked edges recursively.
- **Parameters**:
    - `item_id` (`int`): ID of the todo item to analyze.
    - `direction` (`str`, optional): `'upstream'` (what blocks it), `'downstream'` (what it blocks), or `'both'`. Default: `'both'`.
- **Returns**: `{"item": {...}, "upstream": [...], "downstream": [...]}` — the direction keys omitted when not requested, or an error message.

---

**`assistant-workflow-guide`**

- **Description**: Get a comprehensive workflow guide for code assistants using this system for project management.
- **Parameters**: None.
- **Returns**: `{"guide": "detailed_workflow_guide"}` with complete usage instructions, examples, and best practices.

---

## Contributing

Contributions are welcome! Please open an issue or submit a pull request.

## License

MIT License. See [LICENSE](LICENSE) for details.
