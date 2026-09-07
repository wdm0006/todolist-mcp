"""Regression tests for undated-item ordering under sort_by='due_date' (issue #30).

SQLite orders NULL first on ASC and last on DESC, so `list_items(sort_by="due_date")`
used to put undated items ahead of everything with a real deadline — the opposite of
the default path, which maps a missing due date to `date.max` (undated last).
"""

import os
import tempfile

import pytest
from sqlmodel import SQLModel, create_engine

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


@pytest.fixture(scope="function")
def dated_and_undated(temp_db):
    """Four items: 1 and 3 undated, 2 due 2026-12-01, 4 due 2026-01-05 (issue #30 fixture)."""
    add_item(description="undated one")  # id 1
    add_item(description="late deadline", due_date_str="2026-12-01")  # id 2
    add_item(description="undated two")  # id 3
    add_item(description="early deadline", due_date_str="2026-01-05")  # id 4
    return [1, 2, 3, 4]


def test_due_date_ascending_sorts_undated_last(temp_db, dated_and_undated):
    result = list_items(sort_by="due_date")

    assert [item["id"] for item in result["items"]] == [4, 2, 1, 3]


def test_due_date_descending_keeps_undated_last(temp_db, dated_and_undated):
    result = list_items(sort_by="-due_date")

    assert [item["id"] for item in result["items"]] == [2, 4, 1, 3]


def test_default_ordering_unchanged(temp_db, dated_and_undated):
    # The default path already mapped undated to date.max; it must not move.
    result = list_items()

    assert [item["id"] for item in result["items"]] == [4, 2, 1, 3]


def test_non_nullable_sort_fields_unchanged(temp_db, dated_and_undated):
    result = list_items(sort_by="created_at")

    assert [item["id"] for item in result["items"]] == [1, 2, 3, 4]
