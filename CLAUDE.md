# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

This is a Model Context Protocol (MCP) server for managing a todo list backed by SQLite. It's designed to be used by AI assistants and development tools to interact with a persistent todo list. The server exposes MCP tools for adding, listing, updating, and removing todo items.

## Development Commands

### Setup and Installation
```bash
# Create virtual environment
make setup

# Install dependencies (including dev dependencies)
make install
```

### Development Workflow
```bash
# Run linting (with auto-fix)
make lint

# Format code
make format

# Run tests
make test

# Run the server for testing (requires project directory)
uv run todo_mcp.py --project-dir /path/to/project
```

### Testing
- Tests use pytest with temporary SQLite databases
- Run individual tests: `uv run python -m pytest tests/test_update_item.py::test_name`
- Test fixtures create isolated temporary databases for each test

## Code Architecture

### Core Components

**Main Server (`todo_mcp.py`)**
- Single-file MCP server with embedded dependencies using `/// script` format
- Uses FastMCP framework for MCP protocol implementation
- SQLite database with SQLModel ORM for data persistence
- Database location configurable via `--project-dir` CLI argument

**Data Models**
- `Todo`: Main SQLModel table with fields for description, status, priority, dates, and tags
- `Status` enum: open, in_progress, done, cancelled
- `Priority` enum: high, medium, low
- Automatic timestamp tracking (created_at, updated_at)

**MCP Tools Exposed**
- `add-item`: Create new todo items
- `list-items`: Query todos with filtering and sorting
- `update-item`: Modify existing todo fields
- `mark-item-done`: Quick status change to done
- `remove-item`: Delete todos from database
- `assistant-workflow-guide`: Get comprehensive usage guide for assistants

### Database Design
- SQLite database file named `todo.db` in specified project directory
- Indexed fields for efficient queries: description, status, priority, created_at, due_date, tags
- Automatic table creation on first run

### Error Handling
- Input validation with helpful error messages
- Typo correction suggestions using difflib for enum values
- Database connection and transaction error handling

## Long-term Project Management for Code Assistants

This MCP server is specifically designed for code assistants to manage long-term projects where each todo item represents a PR or development task.

### Recommended PR Workflow

**1. Adding New PR Tasks**
```python
# Add a new PR with descriptive tags
add_item(
    description="Implement OAuth2 authentication with JWT tokens",
    priority="high",
    due_date_str="2024-03-31", 
    tags="backend,security,oauth,feature"
)
```

**2. Grooming Activities**
- Use `list_items()` to review all open items periodically
- Use `update_item()` to refine descriptions, adjust priorities, and update tags
- Use `remove_item()` for obsolete tasks or `update_item(status="cancelled")` to track cancelled work

**3. Work Lifecycle**
```python
# Start work
update_item(item_id=X, status="in_progress")

# Before marking complete, assistant should run tests
# (Manual step - run project's test suite)

# Mark as complete only after tests pass  
mark_item_done(item_id=X)
```

**4. Reporting and Status Tracking**
```python
# Status reports
list_items(status_filter="open")          # Backlog items
list_items(status_filter="in_progress")   # Current work
list_items(status_filter="done")          # Completed PRs

# Priority-based planning
list_items(priority_filter="high", sort_by="due_date")

# Tag-based filtering
list_items(tag_filter="backend,security")  # All backend security tasks
list_items(tag_filter="bugfix")           # All bug fixes
```

### Tagging Strategy for Assistants

Use tags to categorize PRs by:
- **Type**: `feature`, `bugfix`, `enhancement`, `refactor`, `docs`, `testing`
- **Component**: `backend`, `frontend`, `api`, `ui`, `database` 
- **Priority Context**: `security`, `performance`, `accessibility`
- **Release**: `v1.2`, `q1-release`, `hotfix`
- **Size**: `small`, `medium`, `large` (for estimation)

### Testing Integration

Since the MCP server cannot directly run tests, assistants should:
1. Update status to `in_progress` when starting work
2. Implement the changes using other tools
3. Run the project's test suite (use `make test` or equivalent)
4. Only call `mark_item_done()` after confirming tests pass
5. If tests fail, keep status as `in_progress` and document issues in description

### Getting Help
Assistants can call `assistant_workflow_guide()` to get a comprehensive guide with examples, best practices, and detailed workflow instructions. This tool returns the complete usage documentation as a formatted guide.

## Development Notes

### Code Style
- Uses Ruff for linting and formatting (configured in pyproject.toml)
- Target Python 3.10+
- Line length: 120 characters
- Double quotes for strings

### Testing Strategy
- Pytest with temporary database fixtures
- Tests use monkeypatching to replace the global engine
- Each test gets an isolated temporary SQLite file
- Focus on testing MCP tool functions and edge cases
- PR workflow tests in `tests/test_pr_workflow.py` demonstrate usage patterns