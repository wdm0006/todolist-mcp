"""Query-count regression tests for the batched dependency lookups.

``list_dependencies()`` (all-deps branch) and ``get_ready_items()`` used to issue
one query per row (2N+1 and N+1 respectively); both now run a constant number of
queries regardless of graph size. The listener counts real statements at the
engine level, so a regression to N+1 cannot pass silently.

Measured before the batch fix (main, b3aba92):
  - ``list_dependencies()`` with 8 distinct-endpoint edges: 17 queries (2N+1)
  - ``get_ready_items()`` with 28 open items:               29 queries (1+N)
After the fix both calls run 2 queries (verified at fix time); the assertions
below leave headroom for dialect-level statements while still failing any
per-row loop.
"""

import os
import tempfile
from contextlib import contextmanager

import pytest
from sqlalchemy import event
from sqlmodel import SQLModel, create_engine

from todo_mcp import add_dependency, add_item, get_ready_items, list_dependencies


@pytest.fixture(scope="function")
def temp_db(monkeypatch):
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as tf:
        db_url = f"sqlite:///{tf.name}"
    test_engine = create_engine(db_url)
    SQLModel.metadata.create_all(test_engine)
    monkeypatch.setattr("todo_mcp.engine", test_engine)
    yield test_engine
    os.unlink(tf.name)


@contextmanager
def count_queries(engine):
    """Yield the list of SQL statements executed against ``engine`` inside the block."""
    statements = []

    def record(conn, cursor, statement, parameters, context, executemany):
        statements.append(statement)

    event.listen(engine, "before_cursor_execute", record)
    try:
        yield statements
    finally:
        event.remove(engine, "before_cursor_execute", record)


FAN_OUT_EDGES = 10  # 20 distinct endpoint todos -> 2N+1 = 21 queries before the fix


@pytest.fixture(scope="function")
def fan_out_graph(temp_db):
    """Dependency edges over fully distinct todos, so session identity maps cannot mask lookups."""
    for i in range(1, 2 * FAN_OUT_EDGES + 1):
        add_item(description=f"edge-{i}")
    for blocker in range(1, FAN_OUT_EDGES + 1):
        result = add_dependency(blocker_id=blocker, blocked_id=FAN_OUT_EDGES + blocker)
        assert "error" not in result
    return FAN_OUT_EDGES


def test_list_dependencies_query_count_is_constant(temp_db, fan_out_graph):
    with count_queries(temp_db) as statements:
        result = list_dependencies()

    assert "error" not in result
    assert len(result["dependencies"]) == FAN_OUT_EDGES
    # 2 queries: edges + one batched IN lookup. Was 2N+1 = 21 with this fixture.
    assert len(statements) <= 3


def test_get_ready_items_query_count_is_constant(temp_db, fan_out_graph):
    # 5 additional unblocked open items: 25 open items in total, 15 ready.
    for i in range(5):
        add_item(description=f"ready-{i}")

    with count_queries(temp_db) as statements:
        result = get_ready_items()

    assert result["summary"] == {"ready_count": 15, "blocked_count": 10}
    # 2 queries: open items + one batched blocker-edge lookup. Was 1 + N = 26 here.
    assert len(statements) <= 3
