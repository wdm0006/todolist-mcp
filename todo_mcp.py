#!/usr/bin/env python3
# /// script
# dependencies = [
#   "sqlmodel>=0.0.14,<0.1.0",
#   "mcp[cli]>=1.7.0,<2.0.0"
# ]
# ///

import enum
from datetime import datetime, date
from typing import Optional, Dict, Any, Union
import pathlib
import argparse
import sys
import difflib

from sqlmodel import Field, Session, SQLModel, create_engine, select, col
from sqlalchemy import text
from mcp.server.fastmcp import FastMCP


# --- Argument Parsing for Project Directory ---
def parse_cli_args():
    """
    Parse command-line arguments for the project directory.
    Returns:
        argparse.Namespace: Parsed arguments with 'project_dir' attribute.
    """
    parser = argparse.ArgumentParser(description="Todo MCP Server - Database Configuration")
    parser.add_argument(
        "--project-dir",
        type=str,
        required=False,
        help="The absolute path to the project directory where todo.db will be stored.",
    )

    known_args, _ = parser.parse_known_args()
    return known_args


cli_args = parse_cli_args()

# --- Database Setup ---
if cli_args.project_dir:
    PROJECT_DIR_PATH = pathlib.Path(cli_args.project_dir).resolve()
    if not PROJECT_DIR_PATH.is_dir():
        print(
            f"Error: Provided project directory does not exist or is not a directory: {PROJECT_DIR_PATH}",
            file=sys.stderr,
        )
        sys.exit(1)
    DATABASE_FILE = PROJECT_DIR_PATH / "todo.db"
    DATABASE_URL = f"sqlite:///{DATABASE_FILE.resolve()}"
else:
    print(
        "Warning: --project-dir not specified. Defaulting todo.db to script's"
        " directory parent. Use --project-dir for explicit control.",
        file=sys.stderr,
    )
    DATABASE_FILE = pathlib.Path(__file__).resolve().parent.parent / "todo.db"  # Fallback to old logic
    DATABASE_URL = f"sqlite:///{DATABASE_FILE.resolve()}"


engine = create_engine(DATABASE_URL)

# MCP Server instance
mcp_server = FastMCP(
    name="TodoMCP", description="A simple MCP server for managing a todo list. Configure with --project-dir at startup."
)


class Status(str, enum.Enum):
    """Enumeration for todo item status."""

    OPEN = "open"
    IN_PROGRESS = "in_progress"
    DONE = "done"
    CANCELLED = "cancelled"


class Priority(str, enum.Enum):
    """Enumeration for todo item priority."""

    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


# Define a mapping for sorting priorities if needed, e.g., high=1, medium=2, low=3
PRIORITY_ORDER = {Priority.HIGH: 1, Priority.MEDIUM: 2, Priority.LOW: 3}


# Check if the Todo class already exists to prevent redefinition errors
if not hasattr(sys.modules.get(__name__), '_TODO_TABLE_DEFINED'):
    class Todo(SQLModel, table=True, extend_existing=True, sqlite_autoincrement=True):
        """
        SQLModel for a todo item.
        Attributes:
            id (int): Primary key.
            description (str): Short description of the todo item.
            long_description (str, optional): Detailed description with additional context.
            status (Status): Status of the item.
            priority (Priority): Priority level.
            created_at (datetime): Creation timestamp.
            updated_at (datetime): Last update timestamp.
            due_date (date, optional): Due date.
            tags (str, optional): Comma-separated tags.
        """

        id: Optional[int] = Field(default=None, primary_key=True)
        description: str = Field(index=True)
        long_description: Optional[str] = Field(default=None)
        status: Status = Field(default=Status.OPEN, index=True)
        priority: Priority = Field(default=Priority.MEDIUM, index=True)
        created_at: datetime = Field(default_factory=datetime.utcnow, index=True)
        updated_at: datetime = Field(default_factory=datetime.utcnow)
        due_date: Optional[date] = Field(default=None, index=True)
        tags: Optional[str] = Field(default=None, index=True)
    
    # Mark that the table has been defined
    sys.modules[__name__]._TODO_TABLE_DEFINED = True
else:
    # If already defined, get the existing class
    Todo = getattr(sys.modules[__name__], 'Todo', None)


def run_migrations():
    """
    Run database migrations to update existing databases with new schema changes.
    """
    with Session(engine) as session:
        # Create schema_version table if it doesn't exist
        try:
            session.exec(text("""
                CREATE TABLE IF NOT EXISTS schema_version (
                    version INTEGER PRIMARY KEY,
                    applied_at TEXT NOT NULL
                )
            """))
            session.commit()
        except Exception as e:
            print(f"Warning: Could not create schema_version table: {e}")
        
        # Check current schema version
        try:
            result = session.exec(text("SELECT MAX(version) FROM schema_version")).first()
            current_version = result[0] if result and result[0] is not None else 0
        except Exception:
            current_version = 0
        
        # Migration 1: Add long_description column
        if current_version < 1:
            try:
                # Check if column already exists (for databases created after this migration was added)
                session.exec(select(Todo.long_description).limit(1))
                # Column exists, just update version
                session.exec(text("INSERT INTO schema_version (version, applied_at) VALUES (1, datetime('now'))"))
                session.commit()
            except Exception:
                # Column doesn't exist, add it
                print("Migration 1: Adding long_description column to existing database...")
                try:
                    session.exec(text("ALTER TABLE todo ADD COLUMN long_description TEXT"))
                    session.exec(text("INSERT INTO schema_version (version, applied_at) VALUES (1, datetime('now'))"))
                    session.commit()
                    print("Successfully added long_description column")
                except Exception as e:
                    print(f"Warning: Could not add long_description column: {e}")
                    pass


def create_db_and_tables():
    """
    Create the database and tables if they do not exist.
    Also run any necessary migrations for existing databases.
    """
    SQLModel.metadata.create_all(engine)
    run_migrations()


def todo_to_dict(todo_item: Todo) -> Dict[str, Any]:
    """
    Convert a Todo model instance to a dictionary, formatting dates as ISO strings.
    Args:
        todo_item (Todo): The todo item instance.
    Returns:
        dict: Dictionary representation of the todo item.
    """
    item_dict = todo_item.model_dump()
    if item_dict.get("due_date") and isinstance(item_dict["due_date"], date):
        item_dict["due_date"] = item_dict["due_date"].isoformat()
    if item_dict.get("created_at") and isinstance(item_dict["created_at"], datetime):
        item_dict["created_at"] = item_dict["created_at"].isoformat()
    if item_dict.get("updated_at") and isinstance(item_dict["updated_at"], datetime):
        item_dict["updated_at"] = item_dict["updated_at"].isoformat()
    return item_dict


def suggest_correction(value: str, valid_values: list[str]) -> str:
    """
    Suggest the closest valid value using difflib.get_close_matches.
    """
    matches = difflib.get_close_matches(value, valid_values, n=1)
    if matches:
        return f"Did you mean '{matches[0]}'?"
    return ""


# --- Enum Mapping Helpers ---
def parse_status(value: Optional[Union[str, Status]]) -> Optional[Status]:
    """
    Convert a string or Status to a Status enum value.
    Args:
        value (str or Status or None): Input value.
    Returns:
        Status or None: Corresponding Status enum or None.
    Raises:
        ValueError: If the input is not a valid status.
    """
    if value is None or isinstance(value, Status):
        return value
    value_str = str(value).strip().lower()
    for s in Status:
        if value_str == s.value or value_str == s.name.lower():
            return s
    valid = [s.value for s in Status]
    suggestion = suggest_correction(value_str, valid)
    raise ValueError(f"Invalid status: '{value}'. Valid: {valid}. {suggestion}")


def parse_status_list(value: Optional[Union[str, Status, list[str], list[Status]]]) -> Optional[list[Status]]:
    """
    Convert a string, Status, list of strings, or list of Status to a list of Status enums.
    Args:
        value (str, Status, list[str], list[Status], or None): Input value(s).
    Returns:
        list[Status] or None: List of Status enums or None.
    Raises:
        ValueError: If any input is not a valid status.
    """
    if value is None:
        return None
    if isinstance(value, (str, Status)):
        return [parse_status(value)]
    if isinstance(value, list):
        result = []
        for v in value:
            result.append(parse_status(v))
        return result
    raise ValueError(f"Invalid status_filter: {value}")


def parse_priority(value: Optional[Union[str, Priority]]) -> Optional[Priority]:
    """
    Convert a string or Priority to a Priority enum value.
    Args:
        value (str or Priority or None): Input value.
    Returns:
        Priority or None: Corresponding Priority enum or None.
    Raises:
        ValueError: If the input is not a valid priority.
    """
    if value is None or isinstance(value, Priority):
        return value
    value_str = str(value).strip().lower()
    for p in Priority:
        if value_str == p.value or value_str == p.name.lower():
            return p
    valid = [p.value for p in Priority]
    suggestion = suggest_correction(value_str, valid)
    raise ValueError(f"Invalid priority: '{value}'. Valid: {valid}. {suggestion}")


def parse_priority_list(value: Optional[Union[str, Priority, list[str], list[Priority]]]) -> Optional[list[Priority]]:
    if value is None:
        return None
    if isinstance(value, (str, Priority)):
        return [parse_priority(value)]
    if isinstance(value, list):
        result = []
        for v in value:
            result.append(parse_priority(v))
        return result
    raise ValueError(f"Invalid priority_filter: {value}")


def parse_tag_list(value: Optional[Union[str, list[str]]]) -> Optional[list[str]]:
    if value is None:
        return None
    if isinstance(value, str):
        return [value]
    if isinstance(value, list):
        return [str(v) for v in value]
    raise ValueError(f"Invalid tag_filter: {value}")


@mcp_server.tool()
def add_item(
    description: str,
    priority: str = Priority.MEDIUM,
    due_date_str: Optional[str] = None,
    tags: Optional[str] = None,
    long_description: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Add a new todo item.
    Args:
        description (str): Short description of the todo item.
        priority (str, optional): Priority level. Must be one of: 'high', 'medium', 'low'. Defaults to 'medium'.
        due_date_str (str, optional): Due date in YYYY-MM-DD format.
        tags (str, optional): Comma-separated tags.
        long_description (str, optional): Detailed description with additional context, requirements, or notes.
    Returns:
        dict: The created todo item as a dictionary, or an error message.
    """
    try:
        priority_enum = parse_priority(priority)
    except ValueError as e:
        return {"error": str(e)}
    parsed_due_date = None
    if due_date_str:
        try:
            parsed_due_date = datetime.strptime(due_date_str, "%Y-%m-%d").date()
        except ValueError:
            return {"error": f"Invalid date format for due date: '{due_date_str}'. Please use YYYY-MM-DD."}

    with Session(engine) as session:
        todo = Todo(
            description=description,
            long_description=long_description,
            priority=priority_enum,
            due_date=parsed_due_date,
            tags=tags,
            updated_at=datetime.utcnow(),
        )
        session.add(todo)
        session.commit()
        session.refresh(todo)
        return todo_to_dict(todo)


@mcp_server.tool()
def list_items(
    show_all_statuses: bool = False,
    status_filter: Optional[Union[str, Status, list[Union[str, Status]]]] = None,
    priority_filter: Optional[Union[str, Priority, list[Union[str, Priority]]]] = None,
    sort_by: Optional[str] = None,
    tag_filter: Optional[Union[str, list[str]]] = None,
) -> Dict[str, Any]:
    """
    List todo items with optional filters and sorting.

    Args:
        show_all_statuses (bool, optional): If True, show all statuses. Defaults to False.
        status_filter (str, Status, or list[str|Status], optional): Filter by one or more statuses. Each must be one of: 'open', 'in_progress', 'done', 'cancelled'.
        priority_filter (str, Priority, or list[str|Priority], optional): Filter by one or more priorities. Each must be one of: 'high', 'medium', 'low'.
        sort_by (str, optional): Field to sort by. Prefix with '-' for descending. Valid fields: 'priority', 'due_date', 'created_at', 'status', 'description', 'id'.
        tag_filter (str or list[str], optional): Filter by one or more tag substrings (AND logic).

    Returns:
        dict: {"items": [list_of_items]} on success, or {"error": "message"} on failure.

    Example usage:
        list_items()  # List open/in_progress items
        list_items(status_filter="done")
        list_items(status_filter=["open", "done"])
        list_items(priority_filter="high")
        list_items(priority_filter=["high", "medium"])
        list_items(tag_filter="work")
        list_items(tag_filter=["work", "urgent"])
        list_items(sort_by="-priority")

    Valid values:
        status_filter: 'open', 'in_progress', 'done', 'cancelled'
        priority_filter: 'high', 'medium', 'low'
        sort_by: 'priority', 'due_date', 'created_at', 'status', 'description', 'id'
    """
    try:
        status_enums = parse_status_list(status_filter)
    except ValueError as e:
        return {"error": str(e)}
    try:
        priority_enums = parse_priority_list(priority_filter)
    except ValueError as e:
        return {"error": str(e)}
    try:
        tag_list = parse_tag_list(tag_filter)
    except ValueError as e:
        return {"error": str(e)}
    with Session(engine) as session:
        statement = select(Todo)

        if status_enums:
            statement = statement.where(col(Todo.status).in_(status_enums))
        elif not show_all_statuses:
            statement = statement.where(col(Todo.status).in_([Status.OPEN, Status.IN_PROGRESS]))

        if priority_enums:
            statement = statement.where(col(Todo.priority).in_(priority_enums))

        if tag_list:
            for tag in tag_list:
                statement = statement.where(Todo.tags.like(f"%{tag}%"))

        valid_sort_fields = ["priority", "due_date", "created_at", "status", "description", "id"]
        if sort_by:
            descending = sort_by.startswith("-")
            field_name = sort_by[1:] if descending else sort_by

            if field_name not in valid_sort_fields:
                return {"error": f"Invalid sort field '{field_name}'. Valid fields: {valid_sort_fields}"}

            sort_column = getattr(Todo, field_name)

            if field_name != "priority":
                if descending:
                    statement = statement.order_by(sort_column.desc())
                else:
                    statement = statement.order_by(sort_column.asc())

        else:
            statement = statement.order_by(Todo.due_date.asc(), Todo.created_at.asc())

        results = session.exec(statement).all()

        def sort_key(item: Todo):
            return (
                PRIORITY_ORDER[item.priority],
                item.due_date if item.due_date else date.max,
                item.created_at,
            )

        if sort_by:
            descending_sort = sort_by.startswith("-")
            actual_sort_field = sort_by[1:] if descending_sort else sort_by
            if actual_sort_field == "priority":
                results = sorted(results, key=sort_key, reverse=descending_sort)
        else:
            results = sorted(results, key=sort_key)

        processed_results = [todo_to_dict(item) for item in results]
        return {"items": processed_results}


@mcp_server.tool()
def update_item(
    item_id: int,
    description: Optional[str] = None,
    status: Optional[str] = None,
    priority: Optional[str] = None,
    due_date_str: Optional[str] = None,
    tags: Optional[str] = None,
    long_description: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Update an existing todo item. Only provided fields will be changed.
    Args:
        item_id (int): ID of the todo item to update.
        description (str, optional): New short description.
        status (str, optional): New status. Must be one of: 'open', 'in_progress', 'done', 'cancelled'.
        priority (str, optional): New priority. Must be one of: 'high', 'medium', 'low'.
        due_date_str (str, optional): New due date (YYYY-MM-DD) or 'none' to clear.
        tags (str, optional): New tags (comma-separated) or 'none' to clear.
        long_description (str, optional): New detailed description or 'none' to clear.
    Returns:
        dict: The updated todo item as a dictionary, or an error/message.
    """
    with Session(engine) as session:
        todo = session.get(Todo, item_id)
        if not todo:
            return {"error": f"Todo item with ID {item_id} not found."}

        updated = False
        if description is not None:
            todo.description = description
            updated = True
        if status is not None:
            try:
                todo.status = parse_status(status)
            except ValueError as e:
                return {"error": str(e)}
            updated = True
        if priority is not None:
            try:
                todo.priority = parse_priority(priority)
            except ValueError as e:
                return {"error": str(e)}
            updated = True
        if due_date_str is not None:
            if due_date_str.lower() == "none":
                todo.due_date = None
            else:
                try:
                    todo.due_date = datetime.strptime(due_date_str, "%Y-%m-%d").date()
                except ValueError:
                    return {"error": f"Invalid date format for due date: '{due_date_str}'. Use YYYY-MM-DD or 'none'."}
            updated = True
        if tags is not None:
            todo.tags = None if tags.lower() == "none" else tags
            updated = True
        if long_description is not None:
            todo.long_description = None if long_description.lower() == "none" else long_description
            updated = True

        if updated:
            todo.updated_at = datetime.utcnow()
            session.add(todo)
            session.commit()
            session.refresh(todo)
            return todo_to_dict(todo)
        else:
            return {"message": "No changes specified for the item.", "item": todo_to_dict(todo)}


@mcp_server.tool()
def mark_item_done(item_id: int) -> Dict[str, Any]:
    """
    Mark a todo item as DONE.
    Args:
        item_id (int): ID of the todo item to mark as done.
    Returns:
        dict: The updated todo item as a dictionary, or an error message.
    """
    return update_item(item_id=item_id, status=Status.DONE)


@mcp_server.tool()
def remove_item(item_id: int) -> Dict[str, Any]:
    """
    Remove a todo item from the database.
    Args:
        item_id (int): ID of the todo item to remove.
    Returns:
        dict: Message and ID of the removed item, or an error message.
    """
    with Session(engine) as session:
        todo = session.get(Todo, item_id)
        if not todo:
            return {"error": f"Todo item with ID {item_id} not found."}

        item_description = todo.description
        session.delete(todo)
        session.commit()
        return {"message": f"Removed todo item #{item_id}: '{item_description}'", "id": item_id, "status": "removed"}


@mcp_server.tool()
def assistant_workflow_guide() -> Dict[str, str]:
    """
    Returns a comprehensive guide for code assistants on how to use this todo system for long-term project management.
    
    Returns:
        dict: Complete workflow guide with examples and best practices.
    """
    guide = """
# Code Assistant Project Management Workflow Guide

This todo system is designed for long-term project management where each item represents a PR or development task.

## 🚀 Quick Start Workflow

### 1. Adding New PR Tasks
Always add rich metadata when creating tasks:

```
add_item(
    description="Implement OAuth2 authentication with JWT tokens",
    priority="high",  # high, medium, low
    due_date_str="2024-03-31",  # YYYY-MM-DD format
    tags="backend,security,oauth,feature"  # comma-separated
)
```

### 2. Grooming Your Backlog
Regularly review and refine your task list:

```
# Review all open items
list_items()

# Update task after discussion/planning
update_item(
    item_id=123,
    description="Implement OAuth2 with PKCE flow and refresh tokens", 
    priority="high",
    tags="backend,security,oauth,feature,pkce"
)

# Remove obsolete tasks
remove_item(item_id=456)

# Or mark as cancelled to keep history
update_item(item_id=456, status="cancelled")
```

### 3. Work Lifecycle (IMPORTANT!)
Follow this exact sequence:

```
# 1. Start working on a task
update_item(item_id=123, status="in_progress")

# 2. Implement your changes using other tools
# 3. Run the project's test suite (make test, npm test, etc.)
# 4. ONLY mark done if tests pass!
mark_item_done(item_id=123)

# If tests fail, keep as in_progress and document issues:
update_item(
    item_id=123, 
    description="OAuth2 implementation (failing: test_token_refresh)"
)
```

## 📊 Reporting & Status Tracking

### Status Reports
```
list_items(status_filter="open")          # Backlog/todo items
list_items(status_filter="in_progress")   # Current work
list_items(status_filter="done")          # Completed PRs
list_items(show_all_statuses=True)        # Everything
```

### Priority-Based Planning
```
list_items(priority_filter="high", sort_by="due_date")     # Urgent items
list_items(priority_filter=["high", "medium"])             # Multiple priorities
```

### Tag-Based Organization
```
list_items(tag_filter="backend")           # All backend work
list_items(tag_filter="security")          # Security-related tasks
list_items(tag_filter="bugfix")            # All bug fixes
list_items(tag_filter=["frontend", "ui"])  # Multiple tags (AND logic)
```

## 🏷️ Recommended Tagging Strategy

Use consistent tags to categorize your work:

**By Type:**
- `feature` - New functionality
- `bugfix` - Bug repairs  
- `enhancement` - Improvements to existing features
- `refactor` - Code restructuring
- `docs` - Documentation updates
- `testing` - Test additions/fixes

**By Component:**
- `backend`, `frontend`, `api`, `ui`, `database`, `auth`, `payments`

**By Priority Context:**
- `security`, `performance`, `accessibility`, `breaking-change`

**By Release/Timeline:**
- `v1.2`, `q1-release`, `hotfix`, `next-sprint`

**By Size (for estimation):**
- `small`, `medium`, `large`

## 📈 Advanced Usage Patterns

### Sprint Planning
```
# Get high-priority items for next sprint
list_items(
    priority_filter=["high", "medium"],
    tag_filter="small", 
    sort_by="priority"
)
```

### Release Management
```
# Items for next release
list_items(tag_filter="v1.2", sort_by="due_date")

# Security items that need immediate attention
list_items(tag_filter="security", priority_filter="high")
```

### Progress Tracking
```
# Weekly standup report
list_items(status_filter="done", sort_by="-created_at")      # Recent completions
list_items(status_filter="in_progress")                     # Current work
list_items(priority_filter="high", status_filter="open")    # Upcoming priorities
```

## ⚠️ Important Notes

1. **Testing Integration**: This system cannot run tests directly. Always run your project's test suite manually before marking items as done.

2. **Status Discipline**: Only mark items as "done" when:
   - Implementation is complete
   - Tests are passing
   - Code is ready for PR/merge

3. **Tag Consistency**: Establish and stick to consistent tagging conventions across your project.

4. **Regular Grooming**: Review your backlog regularly to update priorities, refine descriptions, and remove obsolete items.

5. **Due Dates**: Use due dates for release planning and deadline tracking.

## 🔄 Example Daily Workflow

```
1. Morning standup:
   - Check: list_items(status_filter="in_progress")
   - Plan: list_items(priority_filter="high", sort_by="due_date")

2. Start new work:
   - update_item(item_id=X, status="in_progress")

3. Before completing:
   - Run tests: make test (or equivalent)
   - If pass: mark_item_done(item_id=X)
   - If fail: document issues in description

4. End of day:
   - Review: list_items(show_all_statuses=True, sort_by="-updated_at")
```

This system scales from small personal projects to large team initiatives. Use it consistently and it will become an invaluable project management tool!
"""
    return {"guide": guide}


if __name__ == "__main__":
    if not cli_args.project_dir:
        print("Error: --project-dir is required when running the server directly.", file=sys.stderr)
        print("Usage: python scripts/todo_mcp.py --project-dir /path/to/your/project_root", file=sys.stderr)
        sys.exit(1)

    print(f"Starting TodoMCP server. Database: {DATABASE_FILE.resolve()}")
    print("Ensure --project-dir is set correctly if not using default.")
    create_db_and_tables()
    mcp_server.run()
