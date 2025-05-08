#!/usr/bin/env python3
# /// script
# dependencies = [
#   "sqlmodel>=0.0.14,<0.1.0",
#   "mcp[cli]>=1.7.0,<2.0.0" 
# ]
# ///

import enum
from datetime import datetime, date
from typing import Optional, List, Dict, Any, Union
import pathlib
import argparse # For command-line arguments
import sys # To ensure we don't exit if mcp has other args

from sqlmodel import Field, Session, SQLModel, create_engine, select, col
from mcp.server.fastmcp import FastMCP # MCP Import

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
        required=False, # Will check for None and handle later if needed for __main__
        help="The absolute path to the project directory where todo.db will be stored."
    )
    # Try to parse known args. If running under mcp[cli] directly, it might not have these args.
    # If __name__ == "__main__", we will make it effectively required.
    known_args, _ = parser.parse_known_args()
    return known_args

cli_args = parse_cli_args()

# --- Database Setup ---
if cli_args.project_dir:
    PROJECT_DIR_PATH = pathlib.Path(cli_args.project_dir).resolve()
    if not PROJECT_DIR_PATH.is_dir():
        print(f"Error: Provided project directory does not exist or is not a directory: {PROJECT_DIR_PATH}", file=sys.stderr)
        sys.exit(1) # Exit if project_dir is provided but invalid
    DATABASE_FILE = PROJECT_DIR_PATH / "todo.db"
    DATABASE_URL = f"sqlite:///{DATABASE_FILE.resolve()}"
else:
    # Default behavior if --project-dir is not provided (e.g. when not run via __main__ or for testing)
    # This could be an in-memory DB or a default local path, or an error if always required.
    # For now, let's default to a local file in the script's dir if not specified, 
    # but recommend --project-dir for explicit control.
    print("Warning: --project-dir not specified. Defaulting todo.db to script's directory parent. Use --project-dir for explicit control.", file=sys.stderr)
    DATABASE_FILE = pathlib.Path(__file__).resolve().parent.parent / "todo.db" # Fallback to old logic
    DATABASE_URL = f"sqlite:///{DATABASE_FILE.resolve()}"


engine = create_engine(DATABASE_URL)

# MCP Server instance
mcp_server = FastMCP(
    name="TodoMCP", 
    description="A simple MCP server for managing a todo list. Configure with --project-dir at startup."
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

class Todo(SQLModel, table=True):
    """
    SQLModel for a todo item.
    Attributes:
        id (int): Primary key.
        description (str): Description of the todo item.
        status (Status): Status of the item.
        priority (Priority): Priority level.
        created_at (datetime): Creation timestamp.
        updated_at (datetime): Last update timestamp.
        due_date (date, optional): Due date.
        tags (str, optional): Comma-separated tags.
    """
    id: Optional[int] = Field(default=None, primary_key=True)
    description: str = Field(index=True)
    status: Status = Field(default=Status.OPEN, index=True)
    priority: Priority = Field(default=Priority.MEDIUM, index=True)
    created_at: datetime = Field(default_factory=datetime.utcnow, index=True)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    due_date: Optional[date] = Field(default=None, index=True)
    tags: Optional[str] = Field(default=None, index=True) # Comma-separated

def create_db_and_tables():
    """
    Create the database and tables if they do not exist.
    """
    SQLModel.metadata.create_all(engine)

# Helper to convert Todo model to dict, ensuring dates are strings
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
    raise ValueError(f"Invalid status: '{value}'. Valid: {[s.value for s in Status]}")

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
    raise ValueError(f"Invalid priority: '{value}'. Valid: {[p.value for p in Priority]}")

@mcp_server.tool()
def add_item(
    description: str,
    priority: str = Priority.MEDIUM,  # Changed from Union[str, Priority]
    due_date_str: Optional[str] = None, # YYYY-MM-DD
    tags: Optional[str] = None # Comma-separated
) -> Dict[str, Any]:
    """
    Add a new todo item.
    Args:
        description (str): Description of the todo item.
        priority (str, optional): Priority level. Must be one of: 'high', 'medium', 'low'. Defaults to 'medium'.
        due_date_str (str, optional): Due date in YYYY-MM-DD format.
        tags (str, optional): Comma-separated tags.
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
            priority=priority_enum,
            due_date=parsed_due_date,
            tags=tags,
            updated_at=datetime.utcnow() # Ensure updated_at is set on creation too
        )
        session.add(todo)
        session.commit()
        session.refresh(todo)
        return todo_to_dict(todo)

@mcp_server.tool()
def list_items(
    show_all_statuses: bool = False,
    status_filter: Optional[str] = None,  # Changed from Optional[Union[str, Status]]
    priority_filter: Optional[str] = None,  # Changed from Optional[Union[str, Priority]]
    sort_by: Optional[str] = None, # 'priority', 'due_date', 'created_at', 'status', 'description', 'id'. Prepended with '-' for desc.
    tag_filter: Optional[str] = None
) -> Dict[str, Any]:
    """
    List todo items with optional filters and sorting.
    Args:
        show_all_statuses (bool, optional): If True, show all statuses. Defaults to False.
        status_filter (str, optional): Filter by status. Must be one of: 'open', 'in_progress', 'done', 'cancelled'.
        priority_filter (str, optional): Filter by priority. Must be one of: 'high', 'medium', 'low'.
        sort_by (str, optional): Field to sort by. Prefix with '-' for descending.
        tag_filter (str, optional): Filter by tag substring.
    Returns:
        dict: {"items": [list_of_items]} on success, or {"error": "message"} on failure.
    """
    try:
        status_enum = parse_status(status_filter)
    except ValueError as e:
        return {"error": str(e)}
    try:
        priority_enum = parse_priority(priority_filter)
    except ValueError as e:
        return {"error": str(e)}
    with Session(engine) as session:
        statement = select(Todo)

        if status_enum:
            statement = statement.where(Todo.status == status_enum)
        elif not show_all_statuses:
            statement = statement.where(col(Todo.status).in_([Status.OPEN, Status.IN_PROGRESS]))

        if priority_enum:
            statement = statement.where(Todo.priority == priority_enum)
        
        if tag_filter:
            statement = statement.where(Todo.tags.like(f"%{tag_filter}%"))

        valid_sort_fields = ["priority", "due_date", "created_at", "status", "description", "id"]
        if sort_by:
            descending = sort_by.startswith("-")
            field_name = sort_by[1:] if descending else sort_by

            if field_name not in valid_sort_fields:
                return {"error": f"Invalid sort field '{field_name}'. Valid fields: {valid_sort_fields}"}
            
            sort_column = getattr(Todo, field_name)
            
            # For priority, we sort post-query for custom enum order
            if field_name != "priority": 
                if descending:
                    statement = statement.order_by(sort_column.desc())
                else:
                    statement = statement.order_by(sort_column.asc())
            # If sorting by priority, or default sort, handle post-query

        else:
            # Default sort order (will be refined post-query for priority)
            statement = statement.order_by(Todo.due_date.asc(), Todo.created_at.asc())

        results = session.exec(statement).all()
        
        # Post-query sorting for priority and default multi-key sort
        def sort_key(item: Todo):
            return (
                PRIORITY_ORDER[item.priority],
                item.due_date if item.due_date else date.max, # Sort None due dates last
                item.created_at
            )

        # Apply sorting
        if sort_by:
            descending_sort = sort_by.startswith("-")
            actual_sort_field = sort_by[1:] if descending_sort else sort_by
            if actual_sort_field == "priority":
                # Sort by custom key if sorting by priority
                results = sorted(results, key=sort_key, reverse=descending_sort)
            # else: other fields are assumed to be handled by DB sort_column if specified earlier
            # If sort_by was a non-priority field, it was applied to 'statement'
            # If results were fetched without specific order for non-priority field here, they remain as fetched.
        else: # Default sort if no sort_by is specified
            results = sorted(results, key=sort_key)

        # Ensure the return is always a list of dictionaries for the success case
        processed_results = [todo_to_dict(item) for item in results]
        return {"items": processed_results}

@mcp_server.tool()
def update_item(
    item_id: int,
    description: Optional[str] = None,
    status: Optional[str] = None,  # Changed from Optional[Union[str, Status]]
    priority: Optional[str] = None,  # Changed from Optional[Union[str, Priority]]
    due_date_str: Optional[str] = None, # YYYY-MM-DD or 'none' to clear
    tags: Optional[str] = None # Comma-separated string or 'none' to clear
) -> Dict[str, Any]:
    """
    Update an existing todo item. Only provided fields will be changed.
    Args:
        item_id (int): ID of the todo item to update.
        description (str, optional): New description.
        status (str, optional): New status. Must be one of: 'open', 'in_progress', 'done', 'cancelled'.
        priority (str, optional): New priority. Must be one of: 'high', 'medium', 'low'.
        due_date_str (str, optional): New due date (YYYY-MM-DD) or 'none' to clear.
        tags (str, optional): New tags (comma-separated) or 'none' to clear.
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
            if due_date_str.lower() == 'none':
                todo.due_date = None
            else:
                try:
                    todo.due_date = datetime.strptime(due_date_str, "%Y-%m-%d").date()
                except ValueError:
                    return {"error": f"Invalid date format for due date: '{due_date_str}'. Use YYYY-MM-DD or 'none'."}
            updated = True
        if tags is not None:
            todo.tags = None if tags.lower() == 'none' else tags
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
        
        item_description = todo.description # store before deleting
        session.delete(todo)
        session.commit()
        return {"message": f"Removed todo item #{item_id}: '{item_description}'", "id": item_id, "status": "removed"}

if __name__ == "__main__":
    # When run directly, --project-dir becomes mandatory.
    # Re-parse with 'required=True' or check if cli_args.project_dir is None.
    if not cli_args.project_dir:
        print("Error: --project-dir is required when running the server directly.", file=sys.stderr)
        print("Usage: python scripts/todo_mcp.py --project-dir /path/to/your/project_root", file=sys.stderr)
        sys.exit(1)
    
    print(f"Starting TodoMCP server. Database: {DATABASE_FILE.resolve()}")
    print("Ensure --project-dir is set correctly if not using default.")
    create_db_and_tables() # Ensure DB and tables exist before starting server
    mcp_server.run() # Starts the MCP server 