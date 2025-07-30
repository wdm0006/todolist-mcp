# Todo List MCP Server

This is a Model Context Protocol (MCP) server for managing a todo list, backed by SQLite. It enables AI assistants and development tools to interact with a persistent, queryable todo list on your local machine. The server exposes a set of tools for adding, listing, updating, and removing todo items, making it easy to integrate task management into your workflow.

MCP servers act as a secure bridge, allowing AI models and language assistants to interact with local applications, tools, or data. This server leverages that protocol to provide todo management capabilities to connected AI clients.

## Features

This server provides the following todo management tools:

- **`add-item`**: Add a new todo item with description, priority, due date, and tags.
- **`list-items`**: List todo items, with optional filters for status, priority, tags, and sorting.
- **`update-item`**: Update fields of an existing todo item (description, status, priority, due date, tags).
- **`mark-item-done`**: Mark a todo item as done.
- **`remove-item`**: Remove a todo item from the database.
- **`assistant-workflow-guide`**: Get a comprehensive workflow guide for code assistants.

## Installation

This server is packaged as a Python script with embedded dependency management using `/// script`.

1. **Prerequisites**:
    - Python 3.10 or higher.
    - `uv` (recommended) or `pip` for dependency management.

2. **Dependencies**: The script will install these automatically if run with `uv` or `pip`:
    - `sqlmodel`
    - `mcp[cli]`

3. **Running the Server**:

You must specify a project directory for the SQLite database using `--project-dir`:

```bash
uv run todo_mcp.py --project-dir /path/to/your/project
```

Or with pip:

```bash
pip install -r requirements.txt
python todo_mcp.py --project-dir /path/to/your/project
```

**MCP Client Configuration Example:**

```json
{
  "mcpServers": {
    "todolist": {
      "command": "uv",
      "args": [
        "--directory",
        "/path/to/this/repo",
        "run",
        "todo_mcp.py",
        "--project-dir",
        "/path/to/your/project"
      ]
    }
  }
}
```

## Usage Examples

You can connect any MCP client (like Claude.ai, Windsurf, or Cursor) to this server. Example prompts for an AI assistant:

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
