#!/usr/bin/env python3
# /// script
# dependencies = [
#   "sqlmodel>=0.0.14,<0.1.0",
#   "fastmcp>=2.14.0,<3.0.0"
# ]
# ///

import enum
import logging
from datetime import datetime, date
from functools import lru_cache
from typing import Optional, Dict, Any, Union, TYPE_CHECKING
import pathlib
import argparse
import sys
import difflib

from sqlmodel import Field, Session, SQLModel, create_engine, select, col
from sqlalchemy import Engine, UniqueConstraint, delete, or_, text
from fastmcp import FastMCP
from utc_timestamp import utc_now

logger = logging.getLogger(__name__)


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


@lru_cache(maxsize=1)
def get_cli_args() -> argparse.Namespace:
    """Parse (and cache) the CLI arguments on first use — never at import time."""
    return parse_cli_args()


def resolve_database_path(args: argparse.Namespace) -> pathlib.Path:
    """
    Resolve the todo.db location from parsed CLI arguments.

    Configuration problems are logged (stderr), never printed to stdout: stray
    stdout corrupts the stdio MCP protocol.
    """
    if args.project_dir:
        project_dir_path = pathlib.Path(args.project_dir).resolve()
        if not project_dir_path.is_dir():
            logger.error("Provided project directory does not exist or is not a directory: %s", project_dir_path)
            raise SystemExit(1)
        return project_dir_path / "todo.db"
    logger.warning(
        "--project-dir not specified. Defaulting todo.db to script's"
        " directory parent. Use --project-dir for explicit control."
    )
    return pathlib.Path(__file__).resolve().parent.parent / "todo.db"  # Fallback to old logic


# --- Database Setup (lazy: importing this module creates nothing) ---
engine: Optional[Engine] = None


def get_engine() -> Engine:
    """Return the shared engine, creating it on first use.

    Tests patch ``todo_mcp.engine`` directly; a non-None engine is returned as-is.
    """
    global engine
    if engine is None:
        database_path = resolve_database_path(get_cli_args()).resolve()
        engine = create_engine(f"sqlite:///{database_path}")
    return engine


# MCP Server instance
mcp_server = FastMCP("TodoMCP")


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
# (TYPE_CHECKING makes mypy analyze the definition branch; at runtime the module-
# namespace guard reuses the existing classes when the module is re-imported.)
if TYPE_CHECKING or "_TODO_TABLE_DEFINED" not in globals():

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
        created_at: datetime = Field(default_factory=utc_now, index=True)
        updated_at: datetime = Field(default_factory=utc_now)
        due_date: Optional[date] = Field(default=None, index=True)
        tags: Optional[str] = Field(default=None, index=True)

    class TodoDependency(SQLModel, table=True, extend_existing=True):
        """
        SQLModel for dependencies between todo items.
        Represents a 'blocking' relationship where blocker_id blocks blocked_id.
        """

        __table_args__ = (UniqueConstraint("blocker_id", "blocked_id", name="uq_tododependency_pair"),)

        id: Optional[int] = Field(default=None, primary_key=True)
        blocker_id: int = Field(foreign_key="todo.id", index=True)
        blocked_id: int = Field(foreign_key="todo.id", index=True)
        created_at: datetime = Field(default_factory=utc_now)

    # Mark that the table has been defined
    globals()["_TODO_TABLE_DEFINED"] = True
else:
    # If already defined, get the existing class
    Todo = getattr(sys.modules[__name__], "Todo", None)
    TodoDependency = getattr(sys.modules[__name__], "TodoDependency", None)


def run_migrations(database_engine=None):
    """
    Run database migrations to update existing databases with new schema changes.
    """
    with Session(database_engine or get_engine()) as session:
        # Create schema_version table if it doesn't exist
        try:
            session.exec(
                text("""
                CREATE TABLE IF NOT EXISTS schema_version (
                    version INTEGER PRIMARY KEY,
                    applied_at TEXT NOT NULL
                )
            """)
            )
            session.commit()
        except Exception:
            logger.warning("Could not create schema_version table", exc_info=True)

        # Check current schema version
        try:
            result = session.exec(text("SELECT MAX(version) FROM schema_version")).first()
            current_version = result[0] if result and result[0] is not None else 0
        except Exception:
            logger.warning("Could not read schema_version; assuming version 0", exc_info=True)
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
                logger.info("Migration 1: Adding long_description column to existing database...")
                try:
                    session.exec(text("ALTER TABLE todo ADD COLUMN long_description TEXT"))
                    session.exec(text("INSERT INTO schema_version (version, applied_at) VALUES (1, datetime('now'))"))
                    session.commit()
                    logger.info("Successfully added long_description column")
                except Exception:
                    logger.warning("Could not add long_description column", exc_info=True)

        # Migration 2: Add TodoDependency table for tracking dependencies
        if current_version < 2:
            try:
                # Check if table already exists
                session.exec(text("SELECT 1 FROM tododependency LIMIT 1"))
                # Table exists, just update version
                session.exec(text("INSERT INTO schema_version (version, applied_at) VALUES (2, datetime('now'))"))
                session.commit()
            except Exception:
                # Table doesn't exist, create it
                logger.info("Migration 2: Creating TodoDependency table for task dependencies...")
                try:
                    session.exec(
                        text("""
                        CREATE TABLE IF NOT EXISTS tododependency (
                            id INTEGER PRIMARY KEY AUTOINCREMENT,
                            blocker_id INTEGER NOT NULL,
                            blocked_id INTEGER NOT NULL,
                            created_at TEXT NOT NULL,
                            FOREIGN KEY (blocker_id) REFERENCES todo(id) ON DELETE CASCADE,
                            FOREIGN KEY (blocked_id) REFERENCES todo(id) ON DELETE CASCADE
                        )
                    """)
                    )
                    session.exec(text("CREATE INDEX IF NOT EXISTS idx_blocker_id ON tododependency(blocker_id)"))
                    session.exec(text("CREATE INDEX IF NOT EXISTS idx_blocked_id ON tododependency(blocked_id)"))
                    session.exec(
                        text(
                            "CREATE UNIQUE INDEX IF NOT EXISTS idx_unique_dependency "
                            "ON tododependency(blocker_id, blocked_id)"
                        )
                    )
                    session.exec(text("INSERT INTO schema_version (version, applied_at) VALUES (2, datetime('now'))"))
                    session.commit()
                    logger.info("Successfully created TodoDependency table")
                except Exception:
                    logger.warning("Could not create TodoDependency table", exc_info=True)

        # Migration 3: Enforce unique dependency pairs on every database
        if current_version < 3:
            try:
                session.exec(
                    text("""
                    DELETE FROM tododependency
                    WHERE id NOT IN (
                        SELECT MIN(id)
                        FROM tododependency
                        GROUP BY blocker_id, blocked_id
                    )
                """)
                )
                session.exec(
                    text(
                        "CREATE UNIQUE INDEX IF NOT EXISTS idx_unique_dependency "
                        "ON tododependency(blocker_id, blocked_id)"
                    )
                )
                session.exec(text("INSERT INTO schema_version (version, applied_at) VALUES (3, datetime('now'))"))
                session.commit()
            except Exception:
                session.rollback()
                logger.warning("Could not enforce unique dependency pairs", exc_info=True)


def create_db_and_tables():
    """
    Create the database and tables if they do not exist.
    Also run any necessary migrations for existing databases.
    """
    SQLModel.metadata.create_all(get_engine())
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
        parsed = parse_status(value)
        if parsed is None:  # value is not None here, so this cannot trigger
            raise ValueError(f"Invalid status_filter: {value}")
        return [parsed]
    if isinstance(value, list):
        result = []
        for v in value:
            parsed = parse_status(v)
            if parsed is None:  # v is not None here, so this cannot trigger
                raise ValueError(f"Invalid status_filter: {v}")
            result.append(parsed)
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
        parsed = parse_priority(value)
        if parsed is None:  # value is not None here, so this cannot trigger
            raise ValueError(f"Invalid priority_filter: {value}")
        return [parsed]
    if isinstance(value, list):
        result = []
        for v in value:
            parsed = parse_priority(v)
            if parsed is None:  # v is not None here, so this cannot trigger
                raise ValueError(f"Invalid priority_filter: {v}")
            result.append(parsed)
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


def has_tags(stored_tags: Optional[str], requested_tags: list[str]) -> bool:
    if stored_tags is None:
        return False
    tags = {tag.strip().casefold() for tag in stored_tags.split(",") if tag.strip()}
    return all(tag.strip().casefold() in tags for tag in requested_tags)


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
    if description is None or not description.strip():
        return {"error": "Description cannot be empty."}
    description = description.strip()
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

    with Session(get_engine()) as session:
        todo = Todo(
            description=description,
            long_description=long_description,
            priority=priority_enum,
            due_date=parsed_due_date,
            tags=tags,
            updated_at=utc_now(),
        )
        session.add(todo)
        session.commit()
        session.refresh(todo)
        return todo_to_dict(todo)


def get_item_by_id(item_id: int) -> Dict[str, Any]:
    """
    Get a specific todo item by its ID.

    Args:
        item_id (int): ID of the todo item to retrieve.

    Returns:
        dict: The todo item as a dictionary, or an error message if not found.
    """
    with Session(get_engine()) as session:
        todo = session.get(Todo, item_id)
        if not todo:
            return {"error": f"Todo item with ID {item_id} not found."}
        return todo_to_dict(todo)


def list_items(
    show_all_statuses: bool = False,
    status_filter: Optional[Union[str, Status, list[Union[str, Status]]]] = None,
    priority_filter: Optional[Union[str, Priority, list[Union[str, Priority]]]] = None,
    sort_by: Optional[str] = None,
    tag_filter: Optional[Union[str, list[str]]] = None,
    limit: Optional[int] = None,
    offset: Optional[int] = None,
) -> Dict[str, Any]:
    """
    List todo items with optional filters, sorting, and pagination.

    Args:
        show_all_statuses (bool, optional): If True, show all statuses. Defaults to False.
        status_filter (str, Status, or list[str|Status], optional): Filter by one or more statuses.
            Each must be one of: 'open', 'in_progress', 'done', 'cancelled'.
        priority_filter (str, Priority, or list[str|Priority], optional): Filter by one or more priorities.
            Each must be one of: 'high', 'medium', 'low'.
        sort_by (str, optional): Field to sort by. Prefix with '-' for descending.
            Valid fields: 'priority', 'due_date', 'created_at', 'status', 'description', 'id', 'updated_at'.
        tag_filter (str or list[str], optional): Filter by one or more exact tags (AND logic).
        limit (int, optional): Maximum number of items to return. Useful for pagination.
            Must be a non-negative integer (0 returns an empty page).
        offset (int, optional): Number of items to skip. Use with limit for pagination.
            Must be a non-negative integer.

    Returns:
        dict: {"items": [list_of_items], "total_count": int} on success, or {"error": "message"} on failure.
        When pagination is used, total_count shows total items before limit/offset are applied.

    Example usage:
        list_items()  # List open/in_progress items
        list_items(status_filter="done")
        list_items(status_filter=["open", "done"])
        list_items(priority_filter="high")
        list_items(priority_filter=["high", "medium"])
        list_items(tag_filter="work")
        list_items(tag_filter=["work", "urgent"])
        list_items(sort_by="-priority")
        list_items(limit=10, offset=20)  # Get items 21-30
        list_items(limit=5)  # Get first 5 items

    Valid values:
        status_filter: 'open', 'in_progress', 'done', 'cancelled'
        priority_filter: 'high', 'medium', 'low'
        sort_by: 'priority', 'due_date', 'created_at', 'status', 'description', 'id', 'updated_at'
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
    # Reject negative pagination values instead of letting them fall through to
    # Python slicing, where they silently count from the end of the results
    # (issue #22). limit=0 stays a valid empty page; offset=0 is the first page.
    if limit is not None and limit < 0:
        return {"error": f"Invalid limit: {limit}. Limit must be a non-negative integer."}
    if offset is not None and offset < 0:
        return {"error": f"Invalid offset: {offset}. Offset must be a non-negative integer."}
    with Session(get_engine()) as session:
        statement = select(Todo)

        if status_enums:
            statement = statement.where(col(Todo.status).in_(status_enums))
        elif not show_all_statuses:
            statement = statement.where(col(Todo.status).in_([Status.OPEN, Status.IN_PROGRESS]))

        if priority_enums:
            statement = statement.where(col(Todo.priority).in_(priority_enums))

        # updated_at is non-nullable, so it takes the generic column path;
        # the assistant guide recommends sort_by="-updated_at" for end-of-day review.
        valid_sort_fields = ["priority", "due_date", "created_at", "status", "description", "id", "updated_at"]
        if sort_by:
            descending = sort_by.startswith("-")
            field_name = sort_by[1:] if descending else sort_by

            if field_name not in valid_sort_fields:
                return {"error": f"Invalid sort field '{field_name}'. Valid fields: {valid_sort_fields}"}

            sort_column = getattr(Todo, field_name)

            if field_name != "priority":
                if field_name == "due_date":
                    # due_date is the only nullable sort field: undated items sort
                    # last in both directions, matching the default path's date.max
                    # semantics (issue #30). The nulls key stays ascending even when
                    # the date column is descending; created_at breaks ties so the
                    # ordering is total.
                    undated_last = col(Todo.due_date).is_(None)
                    if descending:
                        statement = statement.order_by(undated_last, sort_column.desc(), col(Todo.created_at).asc())
                    else:
                        statement = statement.order_by(undated_last, sort_column.asc(), col(Todo.created_at).asc())
                elif descending:
                    statement = statement.order_by(sort_column.desc())
                else:
                    statement = statement.order_by(sort_column.asc())

        else:
            statement = statement.order_by(col(Todo.due_date).asc(), col(Todo.created_at).asc())

        results = session.exec(statement).all()
        if tag_list:
            results = [item for item in results if has_tags(item.tags, tag_list)]

        total_count = len(results)

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

        start = offset or 0
        end = start + limit if limit is not None else len(results)
        results = results[start:end]

        processed_results = [todo_to_dict(item) for item in results]

        # Include total_count in response for pagination metadata
        response: Dict[str, Any] = {"items": processed_results}
        if limit is not None or offset is not None:
            response["total_count"] = total_count

        return response


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

    Only ever update an item to status of done if ALL of the tests for the project are passing.
    Please have a QA Engineer validate the quality of the work before marking the item closed.

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
    with Session(get_engine()) as session:
        todo = session.get(Todo, item_id)
        if not todo:
            return {"error": f"Todo item with ID {item_id} not found."}

        updated = False
        if description is not None:
            if not description.strip():
                return {"error": "Description cannot be empty."}
            todo.description = description.strip()
            updated = True
        if status is not None:
            try:
                parsed_status = parse_status(status)
                if parsed_status is None:  # status is not None here, so this cannot trigger
                    raise ValueError(f"Invalid status: '{status}'.")
                todo.status = parsed_status
            except ValueError as e:
                return {"error": str(e)}
            updated = True
        if priority is not None:
            try:
                parsed_priority = parse_priority(priority)
                if parsed_priority is None:  # priority is not None here, so this cannot trigger
                    raise ValueError(f"Invalid priority: '{priority}'.")
                todo.priority = parsed_priority
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
            todo.updated_at = utc_now()
            session.add(todo)
            session.commit()
            session.refresh(todo)
            return todo_to_dict(todo)
        else:
            return {"message": "No changes specified for the item.", "item": todo_to_dict(todo)}


def mark_item_done(item_id: int) -> Dict[str, Any]:
    """
    Mark a todo item as DONE.

    Only ever update an item to status of done if ALL of the tests for the project are passing.
    Please have a QA Engineer validate the quality of the work before marking the item closed.

    Args:
        item_id (int): ID of the todo item to mark as done.
    Returns:
        dict: The updated todo item as a dictionary, or an error message.
    """
    return update_item(item_id=item_id, status=Status.DONE)


def delete_todo_with_dependencies(session: Session, todo: Todo) -> None:
    """Stage deletion of a todo and every dependency that references it."""
    session.exec(
        delete(TodoDependency).where(
            or_(col(TodoDependency.blocker_id) == todo.id, col(TodoDependency.blocked_id) == todo.id)
        )
    )
    session.delete(todo)


def remove_item(item_id: int) -> Dict[str, Any]:
    """
    Remove a todo item from the database.
    Args:
        item_id (int): ID of the todo item to remove.
    Returns:
        dict: Message and ID of the removed item, or an error message.
    """
    with Session(get_engine()) as session:
        todo = session.get(Todo, item_id)
        if not todo:
            return {"error": f"Todo item with ID {item_id} not found."}

        item_description = todo.description
        delete_todo_with_dependencies(session, todo)
        session.commit()
        return {"message": f"Removed todo item #{item_id}: '{item_description}'", "id": item_id, "status": "removed"}


def add_dependency(blocker_id: int, blocked_id: int) -> Dict[str, Any]:
    """
    Create a dependency between two todo items where one blocks another.

    Args:
        blocker_id (int): ID of the todo item that blocks another.
        blocked_id (int): ID of the todo item that is blocked.

    Returns:
        dict: Success message with dependency details, or an error message.
    """
    if blocker_id == blocked_id:
        return {"error": "A todo item cannot block itself."}

    with Session(get_engine()) as session:
        # Verify both todos exist
        blocker = session.get(Todo, blocker_id)
        if not blocker:
            return {"error": f"Todo item with ID {blocker_id} (blocker) not found."}

        blocked = session.get(Todo, blocked_id)
        if not blocked:
            return {"error": f"Todo item with ID {blocked_id} (blocked) not found."}

        # Check if dependency already exists
        existing = session.exec(
            select(TodoDependency).where(
                (TodoDependency.blocker_id == blocker_id) & (TodoDependency.blocked_id == blocked_id)
            )
        ).first()

        if existing:
            return {"error": f"Dependency already exists: #{blocker_id} blocks #{blocked_id}"}

        # Reject edges that would create a cycle: if blocked_id already reaches
        # blocker_id by following existing blocker->blocked edges, then adding
        # blocker_id -> blocked_id closes a loop.
        visited: set[int] = set()
        stack = [blocked_id]
        while stack:
            current = stack.pop()
            if current == blocker_id:
                return {
                    "error": (
                        f"Adding this dependency would create a circular dependency: "
                        f"#{blocked_id} already blocks #{blocker_id} (directly or transitively)."
                    )
                }
            if current in visited:
                continue
            visited.add(current)
            downstream = session.exec(
                select(TodoDependency.blocked_id).where(TodoDependency.blocker_id == current)
            ).all()
            stack.extend(downstream)

        # Create the dependency
        dependency = TodoDependency(blocker_id=blocker_id, blocked_id=blocked_id, created_at=utc_now())
        session.add(dependency)
        session.commit()
        session.refresh(dependency)

        return {
            "message": (
                f"Created dependency: #{blocker_id} '{blocker.description}' "
                f"blocks #{blocked_id} '{blocked.description}'"
            ),
            "dependency": {
                "id": dependency.id,
                "blocker_id": blocker_id,
                "blocker_description": blocker.description,
                "blocked_id": blocked_id,
                "blocked_description": blocked.description,
                "created_at": dependency.created_at.isoformat(),
            },
        }


def remove_dependency(blocker_id: int, blocked_id: int) -> Dict[str, Any]:
    """
    Remove a dependency between two todo items.

    Args:
        blocker_id (int): ID of the todo item that blocks another.
        blocked_id (int): ID of the todo item that is blocked.

    Returns:
        dict: Success message if removed, or an error message.
    """
    with Session(get_engine()) as session:
        dependency = session.exec(
            select(TodoDependency).where(
                (TodoDependency.blocker_id == blocker_id) & (TodoDependency.blocked_id == blocked_id)
            )
        ).first()

        if not dependency:
            return {"error": f"No dependency found where #{blocker_id} blocks #{blocked_id}"}

        session.delete(dependency)
        session.commit()

        return {"message": f"Removed dependency: #{blocker_id} no longer blocks #{blocked_id}", "status": "removed"}


def list_dependencies(item_id: Optional[int] = None) -> Dict[str, Any]:
    """
    List dependencies for a specific todo item or all dependencies.

    Args:
        item_id (int, optional): ID of a todo item to get dependencies for.
                                If not provided, lists all dependencies.

    Returns:
        dict: List of dependencies with details.
    """
    with Session(get_engine()) as session:
        if item_id:
            # Get specific item's dependencies
            todo = session.get(Todo, item_id)
            if not todo:
                return {"error": f"Todo item with ID {item_id} not found."}

            # Items that block this one
            blocking_query = session.exec(
                select(TodoDependency, Todo)
                .join(Todo, col(TodoDependency.blocker_id) == Todo.id)
                .where(TodoDependency.blocked_id == item_id)
            ).all()

            # Items blocked by this one
            blocked_query = session.exec(
                select(TodoDependency, Todo)
                .join(Todo, col(TodoDependency.blocked_id) == Todo.id)
                .where(TodoDependency.blocker_id == item_id)
            ).all()

            blockers = [
                {
                    "id": dep.blocker_id,
                    "description": blocker.description,
                    "status": blocker.status,
                    "priority": blocker.priority,
                }
                for dep, blocker in blocking_query
            ]

            blocked = [
                {
                    "id": dep.blocked_id,
                    "description": blocked_item.description,
                    "status": blocked_item.status,
                    "priority": blocked_item.priority,
                }
                for dep, blocked_item in blocked_query
            ]

            return {
                "item": {
                    "id": item_id,
                    "description": todo.description,
                    "status": todo.status,
                    "priority": todo.priority,
                },
                "blocked_by": blockers,
                "blocks": blocked,
            }
        else:
            # Two queries total: one for the edges, one batched IN lookup for every
            # referenced todo (was 2N+1 via per-row session.get — N+1 fixed here).
            all_deps = session.exec(select(TodoDependency)).all()
            referenced_ids = {dep.blocker_id for dep in all_deps} | {dep.blocked_id for dep in all_deps}
            todos_by_id: Dict[int, Todo] = {}
            if referenced_ids:
                todos_by_id = {
                    todo.id: todo
                    for todo in session.exec(select(Todo).where(col(Todo.id).in_(referenced_ids))).all()
                    if todo.id is not None
                }

            dependencies = []
            for dep in all_deps:
                blocker = todos_by_id.get(dep.blocker_id)
                blocked_item = todos_by_id.get(dep.blocked_id)

                if blocker and blocked_item:
                    dependencies.append(
                        {
                            "id": dep.id,
                            "blocker": {
                                "id": dep.blocker_id,
                                "description": blocker.description,
                                "status": blocker.status,
                            },
                            "blocked": {
                                "id": dep.blocked_id,
                                "description": blocked_item.description,
                                "status": blocked_item.status,
                            },
                            "created_at": dep.created_at.isoformat(),
                        }
                    )

            return {"dependencies": dependencies}


def get_ready_items() -> Dict[str, Any]:
    """
    Get todo items that are ready to work on (not blocked by incomplete items).

    Returns:
        dict: List of todo items that are not blocked or whose blockers are all done.
    """
    with Session(get_engine()) as session:
        # Two queries total: the open/in-progress items, then every incomplete
        # blocker edge batch-loaded and grouped by blocked item (was 1 + N
        # per-item queries — N+1 fixed here).
        all_items = session.exec(select(Todo).where(col(Todo.status).in_([Status.OPEN, Status.IN_PROGRESS]))).all()

        blocker_edges = session.exec(
            select(TodoDependency, Todo)
            .join(Todo, col(TodoDependency.blocker_id) == Todo.id)
            .where(col(Todo.status).not_in([Status.DONE, Status.CANCELLED]))
        ).all()
        blockers_by_item: Dict[int, list] = {}
        for dep, blocker in blocker_edges:
            blockers_by_item.setdefault(dep.blocked_id, []).append(blocker)

        ready_items = []
        blocked_items = []

        for item in all_items:
            if item.id is None:  # unreachable for rows returned by a SELECT
                continue
            # Check if this item is blocked by any incomplete items
            blockers = blockers_by_item.get(item.id, [])

            if not blockers:
                # Not blocked or all blockers are complete
                ready_items.append(todo_to_dict(item))
            else:
                blocked_items.append(
                    {
                        **todo_to_dict(item),
                        "blocked_by": [
                            {"id": b.id, "description": b.description, "status": b.status} for b in blockers
                        ],
                    }
                )

        # Sort ready items by priority and due date
        def sort_key(item: dict):
            priority_val = PRIORITY_ORDER.get(Priority(item["priority"]), 999)
            due_date_val = datetime.strptime(item["due_date"], "%Y-%m-%d").date() if item.get("due_date") else date.max
            return (priority_val, due_date_val)

        ready_items.sort(key=sort_key)

        return {
            "ready": ready_items,
            "blocked": blocked_items,
            "summary": {"ready_count": len(ready_items), "blocked_count": len(blocked_items)},
        }


def get_dependency_chain(item_id: int, direction: str = "both") -> Dict[str, Any]:
    """
    Get the full dependency chain for a todo item.

    Args:
        item_id (int): ID of the todo item to analyze.
        direction (str): Direction to traverse - "upstream" (blockers), "downstream" (blocked), or "both".

    Returns:
        dict: Full dependency chain with all related items.
    """
    if direction not in ["upstream", "downstream", "both"]:
        return {"error": "Direction must be 'upstream', 'downstream', or 'both'"}

    with Session(get_engine()) as session:
        todo = session.get(Todo, item_id)
        if not todo:
            return {"error": f"Todo item with ID {item_id} not found."}

        def get_upstream(tid: int, visited: set) -> list:
            """Recursively get all items that block this one."""
            if tid in visited:
                return []
            visited.add(tid)

            blockers = session.exec(
                select(Todo)
                .join(TodoDependency, col(TodoDependency.blocker_id) == Todo.id)
                .where(TodoDependency.blocked_id == tid)
            ).all()

            result = []
            for blocker in blockers:
                if blocker.id is None:  # unreachable for rows returned by a SELECT
                    continue
                if blocker.id in visited:  # already listed via another path (reconvergent graph)
                    continue
                result.append(
                    {
                        "id": blocker.id,
                        "description": blocker.description,
                        "status": blocker.status,
                        "priority": blocker.priority,
                        "blockers": get_upstream(blocker.id, visited),
                    }
                )
            return result

        def get_downstream(tid: int, visited: set) -> list:
            """Recursively get all items blocked by this one."""
            if tid in visited:
                return []
            visited.add(tid)

            blocked = session.exec(
                select(Todo)
                .join(TodoDependency, col(TodoDependency.blocked_id) == Todo.id)
                .where(TodoDependency.blocker_id == tid)
            ).all()

            result = []
            for blocked_item in blocked:
                if blocked_item.id is None:  # unreachable for rows returned by a SELECT
                    continue
                if blocked_item.id in visited:  # already listed via another path (reconvergent graph)
                    continue
                result.append(
                    {
                        "id": blocked_item.id,
                        "description": blocked_item.description,
                        "status": blocked_item.status,
                        "priority": blocked_item.priority,
                        "blocked": get_downstream(blocked_item.id, visited),
                    }
                )
            return result

        chain: Dict[str, Any] = {
            "item": {"id": item_id, "description": todo.description, "status": todo.status, "priority": todo.priority}
        }

        if direction in ["upstream", "both"]:
            chain["upstream"] = get_upstream(item_id, set())

        if direction in ["downstream", "both"]:
            chain["downstream"] = get_downstream(item_id, set())

        return chain


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

## 🔍 Retrieving Specific Items

For very large kanbans where list output becomes overwhelming, you can retrieve individual tickets:

```
# Get complete details for a specific ticket number
get_item_by_id(item_id=81)

# Returns all fields: description, status, priority, dates, tags, etc.
# Useful when agents need to examine specific tickets without parsing large lists
```

## 📊 Reporting & Status Tracking

### Status Reports
```
list_items(status_filter="open")          # Backlog/todo items
list_items(status_filter="in_progress")   # Current work
list_items(status_filter="done")          # Completed PRs
list_items(show_all_statuses=True)        # Everything

# For large kanbans, use pagination to manage output
list_items(limit=10)                       # First 10 items
list_items(limit=10, offset=20)           # Items 21-30
list_items(status_filter="done", limit=5) # Last 5 completed items

# Get specific item details by ticket number
get_item_by_id(item_id=81)                # Get details for ticket #81
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

## 🔗 Dependency Management

### Creating Dependencies
Track which tasks block others:

```
# Task 1 must be completed before Task 2 can start
add_dependency(blocker_id=1, blocked_id=2)

# Multiple dependencies
add_dependency(blocker_id=1, blocked_id=3)  # Task 1 also blocks Task 3
add_dependency(blocker_id=2, blocked_id=4)  # Task 2 blocks Task 4
```

### Managing Dependencies
```
# View all dependencies for a task
list_dependencies(item_id=2)  # Shows what blocks task 2 and what it blocks

# View all dependencies in the system
list_dependencies()  # Shows all dependency relationships

# Remove a dependency
remove_dependency(blocker_id=1, blocked_id=2)
```

### Finding Ready Work
```
# Get items ready to work on (not blocked or blockers are done)
get_ready_items()

# Returns:
# - ready: List of items you can start immediately
# - blocked: List of items waiting on dependencies
# - summary: Counts of ready vs blocked items
```

### Analyzing Dependency Chains
```
# See the full dependency tree for a task
get_dependency_chain(item_id=5, direction="both")

# Options:
# - direction="upstream": See all tasks that must complete first
# - direction="downstream": See all tasks waiting on this one
# - direction="both": See the complete dependency network
```

### Dependency Best Practices

1. **Epic Dependencies**: Break large features into subtasks with dependencies
   ```
   # Epic: User Authentication
   add_item(description="Design auth database schema", tags="auth,backend")  # ID: 1
   add_item(description="Implement JWT token generation", tags="auth,backend")  # ID: 2
   add_item(description="Create login API endpoint", tags="auth,api")  # ID: 3
   add_item(description="Build login UI component", tags="auth,frontend")  # ID: 4
   
   # Set up dependencies
   add_dependency(blocker_id=1, blocked_id=2)  # Schema before implementation
   add_dependency(blocker_id=2, blocked_id=3)  # Token logic before API
   add_dependency(blocker_id=3, blocked_id=4)  # API before UI
   ```

2. **Cross-Team Dependencies**: Track when frontend waits on backend
   ```
   add_dependency(blocker_id=backend_api_task_id, blocked_id=frontend_integration_task_id)
   ```

3. **Infrastructure Dependencies**: Ensure setup tasks complete first
   ```
   add_dependency(blocker_id=database_setup_id, blocked_id=migration_task_id)
   ```

## ⚠️ Important Notes

1. **Testing Integration**: This system cannot run tests directly. Always run your project's 
   test suite manually before marking items as done.

2. **Status Discipline**: Only mark items as "done" when:
   - Implementation is complete
   - Tests are passing
   - Code is ready for PR/merge
   - All dependent tasks are unblocked

3. **Tag Consistency**: Establish and stick to consistent tagging conventions across your project.

4. **Regular Grooming**: Review your backlog regularly to update priorities, refine descriptions,
   and remove obsolete items.

5. **Due Dates**: Use due dates for release planning and deadline tracking.

6. **Dependency Hygiene**: Remove dependencies when requirements change to keep the graph clean.

## 🔄 Example Daily Workflow

```
1. Morning standup:
   - Check: list_items(status_filter="in_progress")
   - Plan: get_ready_items()  # See what's not blocked
   - Review: list_dependencies()  # Check dependency status

2. Start new work:
   - Pick from get_ready_items() results
   - update_item(item_id=X, status="in_progress")

3. Before completing:
   - Run tests: make test (or equivalent)
   - If pass: mark_item_done(item_id=X)
   - If fail: document issues in description
   - Check: list_dependencies(item_id=X) to see what gets unblocked

4. End of day:
   - Review: list_items(show_all_statuses=True, sort_by="-updated_at")
   - Plan tomorrow: get_ready_items()
```

This system scales from small personal projects to large team initiatives. Use it consistently
and it will become an invaluable project management tool!
"""
    return {"guide": guide}


# --- Register tools with MCP server (explicit registration keeps functions callable) ---
mcp_server.tool()(add_item)
mcp_server.tool()(get_item_by_id)
mcp_server.tool()(list_items)
mcp_server.tool()(update_item)
mcp_server.tool()(mark_item_done)
mcp_server.tool()(remove_item)
mcp_server.tool()(add_dependency)
mcp_server.tool()(remove_dependency)
mcp_server.tool()(list_dependencies)
mcp_server.tool()(get_ready_items)
mcp_server.tool()(get_dependency_chain)
mcp_server.tool()(assistant_workflow_guide)


def main():
    """Entry point for the TodoList MCP server."""
    # Server diagnostics go to stderr: stdout carries the stdio MCP protocol.
    logging.basicConfig(level=logging.INFO, stream=sys.stderr)
    args = get_cli_args()
    if not args.project_dir:
        logger.error("--project-dir is required when running the server directly.")
        print("Usage: todolist-mcp --project-dir /path/to/your/project_root", file=sys.stderr)
        sys.exit(1)

    logger.info("Starting TodoMCP server. Database: %s", resolve_database_path(args).resolve())
    create_db_and_tables()
    mcp_server.run()


if __name__ == "__main__":
    main()
