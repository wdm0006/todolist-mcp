import os
import tempfile

import pytest
from sqlmodel import Session, SQLModel, create_engine, select

from todo_mcp import Priority, Todo, add_item, update_item


@pytest.fixture(scope="function")
def temp_db(monkeypatch):
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as tf:
        db_url = f"sqlite:///{tf.name}"
    test_engine = create_engine(db_url)
    SQLModel.metadata.create_all(test_engine)
    monkeypatch.setattr("todo_mcp.engine", test_engine)
    yield test_engine
    os.unlink(tf.name)


@pytest.fixture(scope="function")
def sample_todo(temp_db):
    with Session(temp_db) as session:
        todo = Todo(description="Existing item", priority=Priority.MEDIUM)
        session.add(todo)
        session.commit()
        session.refresh(todo)
        return todo.id


def _row_count(engine):
    with Session(engine) as session:
        return len(session.exec(select(Todo)).all())


@pytest.mark.parametrize("bad_description", ["", "   ", "\t\n"])
def test_add_item_rejects_empty_description(temp_db, bad_description):
    result = add_item(description=bad_description)
    assert "error" in result
    assert _row_count(temp_db) == 0


def test_add_item_accepts_valid_description(temp_db):
    result = add_item(description="A real task")
    assert "error" not in result
    assert result["description"] == "A real task"
    assert _row_count(temp_db) == 1


def test_add_item_trims_description(temp_db):
    result = add_item(description="  padded task  ")
    assert result["description"] == "padded task"


@pytest.mark.parametrize("bad_description", ["", "   ", "\t\n"])
def test_update_item_rejects_empty_description(temp_db, sample_todo, bad_description):
    result = update_item(item_id=sample_todo, description=bad_description)
    assert "error" in result
    with Session(temp_db) as session:
        todo = session.get(Todo, sample_todo)
        assert todo.description == "Existing item"


def test_update_item_none_description_leaves_unchanged(temp_db, sample_todo):
    result = update_item(item_id=sample_todo, description=None, priority="high")
    assert result["priority"] == "high"
    assert result["description"] == "Existing item"


def test_update_item_valid_description(temp_db, sample_todo):
    result = update_item(item_id=sample_todo, description="Updated task")
    assert result["description"] == "Updated task"
