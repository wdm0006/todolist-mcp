# Todolist MCP

A Model Context Protocol (MCP) server for managing a todo list backed by SQLite. Enables AI assistants to interact with a persistent, queryable todo list for project management and task tracking.

## Features

The server provides the following tools:

- **`add-item`**: Add a new todo item with description, priority, due date, and tags.
- **`list-items`**: List todo items, with optional filters for status, priority, tags, and sorting.
- **`update-item`**: Update fields of an existing todo item (description, status, priority, due date, tags).
- **`mark-item-done`**: Mark a todo item as done.
- **`remove-item`**: Remove a todo item from the database.
- **`assistant-workflow-guide`**: Get a comprehensive workflow guide for code assistants.

## Installation

Requires Python 3.10+ and `uv`.

1. **Dependencies**: The script will install these automatically if run with `uv`:
    - `sqlmodel` and `fastmcp`

## Running the Server

You must specify a project directory for the SQLite database using `--project-dir`:

```bash
uv run todo_mcp.py --project-dir /path/to/your/project
```

## MCP Client Configuration

```json
{
  "mcpServers": {
    "todolist": {
      "command": "uv",
      "args": [
        "--directory", "/path/to/this/repo",
        "run", "todo_mcp.py",
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

---

**`add-item`**

- **Description**: Add a new todo item.
- **Parameters**:
    - `description` (`str`): Description of the todo item.
    - `priority` (`str`, optional): One of `'high'`, `'medium'`, `'low'`. Default: `'medium'`.
    - `due_date_str` (`str`, optional): Due date in `YYYY-MM-DD` format.
    - `tags` (`str`, optional): Comma-separated tags.
- **Returns**: The created todo item as a dictionary, or an error message.

---

**`list-items`**

- **Description**: List todo items with optional filters and sorting.
- **Parameters**:
    - `show_all_statuses` (`bool`, optional): If `True`, show all statuses. Default: `False`.
    - `status_filter` (`str`, optional): Filter by status (`'open'`, `'in_progress'`, `'done'`, `'cancelled'`).
    - `priority_filter` (`str`, optional): Filter by priority (`'high'`, `'medium'`, `'low'`).
    - `sort_by` (`str`, optional): Field to sort by (`'priority'`, `'due_date'`, `'created_at'`, `'status'`, `'description'`, `'id'`). Prefix with `-` for descending.
    - `tag_filter` (`str`, optional): Filter by tag substring.
- **Returns**: `{"items": [list_of_items]}` or `{"error": "message"}`.

---

**`update-item`**

- **Description**: Update fields of an existing todo item.
- **Parameters**:
    - `item_id` (`int`): ID of the todo item.
    - `description` (`str`, optional): New description.
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

**`assistant-workflow-guide`**

- **Description**: Get a comprehensive workflow guide for code assistants using this system for project management.
- **Parameters**: None.
- **Returns**: `{"guide": "detailed_workflow_guide"}` with complete usage instructions, examples, and best practices.

---

## Contributing

Contributions are welcome! Please open an issue or submit a pull request.

## License

MIT License. See [LICENSE](LICENSE) for details.
