import pytest
from sqlmodel import SQLModel, Session, create_engine
from datetime import datetime
from todo_mcp import Todo, Status, Priority, update_item, add_item, engine

import tempfile
import os

@pytest.fixture(scope="function")
def temp_db(monkeypatch):
    # Create a temporary SQLite file
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as tf:
        db_url = f"sqlite:///{tf.name}"
    test_engine = create_engine(db_url)
    SQLModel.metadata.create_all(test_engine)
    monkeypatch.setattr("todo_mcp.engine", test_engine)
    yield test_engine
    os.unlink(tf.name)

@pytest.fixture(scope="function")
def sample_todo(temp_db):
    # Add a sample todo item
    with Session(temp_db) as session:
        todo = Todo(description="Test item", priority=Priority.MEDIUM)
        session.add(todo)
        session.commit()
        session.refresh(todo)
        return todo.id

def test_update_status_in_progress(temp_db, sample_todo):
    # Should allow status as string 'in_progress'
    result = update_item(item_id=sample_todo, status="in_progress")
    assert result["status"] == "in_progress"
    assert result["id"] == sample_todo

def test_update_status_invalid(temp_db, sample_todo):
    # Should return error for invalid status
    result = update_item(item_id=sample_todo, status="not_a_status")
    assert "error" in result
    assert "Invalid status" in result["error"]

def test_update_priority_string(temp_db, sample_todo):
    # Should allow priority as string
    result = update_item(item_id=sample_todo, priority="high")
    assert result["priority"] == "high"

def test_update_multiple_fields(temp_db, sample_todo):
    # Should update multiple fields
    result = update_item(item_id=sample_todo, status="done", priority="low", description="Updated desc")
    assert result["status"] == "done"
    assert result["priority"] == "low"
    assert result["description"] == "Updated desc"

def test_update_item_not_found(temp_db):
    # Should return error for non-existent item
    result = update_item(item_id=9999, status="done")
    assert "error" in result
    assert "not found" in result["error"] 