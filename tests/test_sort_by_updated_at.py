"""Regression tests for sort_by='updated_at'.

The assistant workflow guide recommends list_items(show_all_statuses=True,
sort_by="-updated_at") for end-of-day review, but 'updated_at' was missing
from the valid sort fields — the guide's own example returned
"Invalid sort field 'updated_at'".
"""

import os
import tempfile
from datetime import datetime

import pytest
from sqlmodel import SQLModel, create_engine

import todo_mcp
from todo_mcp import add_item, list_items


@pytest.fixture(scope="function")
def temp_db(monkeypatch):
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as tf:
        db_url = f"sqlite:///{tf.name}"
    test_engine = create_engine(db_url)
    SQLModel.metadata.create_all(test_engine)
    monkeypatch.setattr("todo_mcp.engine", test_engine)
    yield test_engine
    os.unlink(tf.name)


def pin_updated_at(item_id: int, when: datetime) -> None:
    """Write updated_at directly so ordering is deterministic regardless of test speed."""
    with todo_mcp.Session(todo_mcp.get_engine()) as session:
        item = session.get(todo_mcp.Todo, item_id)
        item.updated_at = when
        session.add(item)
        session.commit()


@pytest.fixture(scope="function")
def three_items_distinct_updates(temp_db):
    """Items 1/2/3 pinned to timestamps so SQL ordering has no ties."""
    t0 = datetime(2026, 9, 1, 12, 0, 0)
    for description in ("first", "second", "third"):
        add_item(description=description)
    pin_updated_at(1, t0)
    pin_updated_at(2, datetime(2026, 9, 2, 12, 0, 0))
    pin_updated_at(3, datetime(2026, 9, 3, 12, 0, 0))
    return t0


def test_updated_at_ascending(three_items_distinct_updates):
    result = list_items(show_all_statuses=True, sort_by="updated_at")

    assert [item["id"] for item in result["items"]] == [1, 2, 3]


def test_updated_at_descending(three_items_distinct_updates):
    result = list_items(show_all_statuses=True, sort_by="-updated_at")

    assert [item["id"] for item in result["items"]] == [3, 2, 1]


def test_assistant_guide_example_returns_no_error(three_items_distinct_updates):
    """The exact call the assistant_workflow_guide recommends must keep working."""
    result = list_items(show_all_statuses=True, sort_by="-updated_at")

    assert "error" not in result
    assert len(result["items"]) == 3


def test_invalid_sort_field_still_rejected(three_items_distinct_updates):
    result = list_items(sort_by="bogus")

    assert "error" in result
    assert "'bogus'" in result["error"]
    assert "updated_at" in result["error"]
