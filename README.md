# MCP Servers Collection

This repository contains Model Context Protocol (MCP) servers designed for AI-powered development workflows. These servers enable specialized AI subagents to manage different aspects of software development through standardized protocols.

## AI Coding Workflow Integration

In modern AI coding workflows, different specialized subagents handle specific responsibilities:

**🎯 Project Manager Subagent** uses the **Todo List MCP Server** to:
- Track long-term project tasks and milestones
- Manage task priorities and deadlines
- Monitor development progress across features
- Coordinate work between different development phases

**🔬 QA Subagent** uses the **Makefile MCP Server** to:
- Run test suites consistently before task completion
- Execute linting and code quality checks
- Perform build verification and deployment steps
- Ensure code standards are met before sign-off

This separation of concerns allows each subagent to specialize in their domain while maintaining a coordinated development process. The Project Manager can create and track tasks, while the QA subagent ensures quality gates are met before the Project Manager marks tasks as complete.

### Example Workflow

1. **Project Manager** creates a new feature task:
   ```
   "Add OAuth2 authentication with JWT tokens, high priority, due March 31st, tags: backend,security,feature"
   ```

2. **Developer** implements the feature and updates status:
   ```
   "Update task #123 to in_progress status"
   ```

3. **QA Subagent** runs quality checks before completion:
   ```
   "Run the test suite" → executes make_test
   "Run linting checks" → executes make_lint  
   "Check code formatting" → executes make_format
   ```

4. **Project Manager** marks task complete only after QA approval:
   ```
   "Mark task #123 as done" → only after all tests pass
   ```

This ensures consistent quality gates and prevents incomplete work from being marked as finished.

## Available Servers

### 1. Todo List MCP Server (`todo_mcp.py`)
A todo list management server backed by SQLite. Enables AI assistants to interact with a persistent, queryable todo list for project management and task tracking. Perfect for project manager subagents to maintain oversight of development workflows.

### 2. Makefile MCP Server (`makefile_mcp.py`) 
A server that exposes Makefile targets as executable tools. AI assistants can discover and execute make targets, with support for filtering which targets are available. Ideal for QA subagents to consistently run test suites, linting, and build processes.

## Todo List MCP Server Features

The todo server provides the following tools:

- **`add-item`**: Add a new todo item with description, priority, due date, and tags.
- **`list-items`**: List todo items, with optional filters for status, priority, tags, and sorting.
- **`update-item`**: Update fields of an existing todo item (description, status, priority, due date, tags).
- **`mark-item-done`**: Mark a todo item as done.
- **`remove-item`**: Remove a todo item from the database.
- **`assistant-workflow-guide`**: Get a comprehensive workflow guide for code assistants.

## Makefile MCP Server Features

The makefile server provides the following tools:

- **Dynamic Make Target Tools**: Each Makefile target becomes an executable tool (e.g., `make_build`, `make_test`, `make_clean`)
- **`list-available-targets`**: List all available make targets exposed by the server
- **`get-makefile-info`**: Get detailed information about the Makefile and filtering configuration

**Key Features:**
- **Target Discovery**: Automatically parses Makefiles to discover targets and descriptions
- **Comment-based Descriptions**: Uses comments above targets as tool descriptions
- **Include/Exclude Filtering**: Filter which targets are exposed as tools via command-line flags
- **Dry Run Support**: Execute targets with `--dry-run` to see what would be executed
- **Additional Arguments**: Pass extra arguments to make commands
- **Error Handling**: Comprehensive error reporting for failed executions
- **Working Directory Control**: Execute make commands in the correct directory

## Installation

These servers are packaged as Python scripts with embedded dependency management using `/// script`.

1. **Prerequisites**:
    - Python 3.10 or higher.
    - `uv` (recommended) or `pip` for dependency management.

2. **Dependencies**: The scripts will install these automatically if run with `uv`:
    - `sqlmodel` and `mcp[cli]` for the todo server
    - `mcp[cli]` for the makefile server

## Running the Servers

### Todo List MCP Server

You must specify a project directory for the SQLite database using `--project-dir`:

```bash
uv run todo_mcp.py --project-dir /path/to/your/project
```

### Makefile MCP Server

```bash
# Use default Makefile in current directory
uv run makefile_mcp.py

# Use specific Makefile
uv run makefile_mcp.py --makefile /path/to/Makefile

# Include only specific targets
uv run makefile_mcp.py --include build,test,clean

# Exclude specific targets  
uv run makefile_mcp.py --exclude deploy,publish

# Custom working directory
uv run makefile_mcp.py --working-dir /path/to/project
```

## MCP Client Configuration

### For AI Subagent Workflows

Configure different MCP servers for specialized subagents:

**Project Manager Subagent** - Gets access to todo management:
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

**QA Subagent** - Gets access to build and test tools:
```json
{
  "mcpServers": {
    "makefile": {
      "command": "uv", 
      "args": [
        "--directory", "/path/to/this/repo",
        "run", "makefile_mcp.py",
        "--makefile", "/path/to/your/project/Makefile",
        "--exclude", "deploy,publish"
      ]
    }
  }
}
```

**Combined Configuration** - For single agents with both responsibilities:
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
    },
    "makefile": {
      "command": "uv", 
      "args": [
        "--directory", "/path/to/this/repo",
        "run", "makefile_mcp.py",
        "--makefile", "/path/to/your/project/Makefile",
        "--exclude", "deploy,publish"
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

### Makefile Examples

**Discovering Available Targets:**
- "What make targets are available?" (Calls `list-available-targets`)
- "Show me information about the Makefile." (Calls `get-makefile-info`)

**Running Make Targets:**
- "Build the project." (Calls `make_build` tool)
- "Run the tests." (Calls `make_test` tool)
- "Clean up build artifacts." (Calls `make_clean` tool)

**Advanced Make Operations:**
- "Run tests with verbose output and 4 parallel jobs." (Calls `make_test` with `additional_args="-j4 VERBOSE=1"`)
- "Show me what the build target would do without actually running it." (Calls `make_build` with `dry_run=True`)
- "Install the project with sudo privileges." (Calls `make_install` with `additional_args="SUDO=sudo"`)

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
