#!/usr/bin/env python3
"""Mutation-campaign hardening tests.

Each test here kills a specific cluster of surviving mutants from the mutmut
campaign over todo_mcp.py (see docs/mutation-waivers.md for the register and
scope). Grouped by the subsystem whose test coverage was thin:

- migrations: version flow, index creation, idempotence
- get_ready_items: priority/due-date ordering and blocked_by shape
- list_items: every documented sort field in both directions
- add/update/remove item: "none" clearing, empty/invalid input errors
- dependency tools: exact response shapes, exact-edge removal, traversal
- parsers and CLI: validation errors, suggestions, path resolution
- todo_to_dict: datetime/date ISO serialization
"""

import pathlib
import sys
import tempfile
import unittest.mock
from datetime import date, datetime, timedelta

import pytest
from sqlmodel import Session, create_engine

sys.path.insert(0, str(pathlib.Path(__file__).parent.parent))

import todo_mcp  # noqa: E402
from todo_mcp import (  # noqa: E402
    Priority,
    Status,
    add_dependency,
    add_item,
    get_dependency_chain,
    get_ready_items,
    list_dependencies,
    list_items,
    parse_priority,
    parse_priority_list,
    parse_status,
    parse_status_list,
    remove_dependency,
    remove_item,
    resolve_database_path,
    suggest_correction,
    todo_to_dict,
    update_item,
)


@pytest.fixture
def temp_db():
    """Temporary database with the shared engine patched (campaign fixture)."""
    with tempfile.TemporaryDirectory() as temp_dir:
        temp_engine = create_engine(f"sqlite:///{temp_dir}/test_todo.db")
        with unittest.mock.patch.object(todo_mcp, "engine", temp_engine):
            todo_mcp.SQLModel.metadata.create_all(temp_engine)
            todo_mcp.run_migrations()
            yield temp_engine


# ---------------------------------------------------------------------------
# Migrations: version flow, indexes, idempotence
# ---------------------------------------------------------------------------


def _scalar_rows(engine, sql):
    with Session(engine) as session:
        return [row[0] for row in session.exec(todo_mcp.text(sql)).all()]


def test_run_migrations_fresh_database_records_migrations_two_and_three():
    """A database with no tables gets migrations 2 and 3 (migration 1 needs the todo table)."""
    with tempfile.TemporaryDirectory() as temp_dir:
        engine = create_engine(f"sqlite:///{temp_dir}/fresh.db")
        todo_mcp.run_migrations(engine)
        versions = _scalar_rows(engine, "SELECT version FROM schema_version ORDER BY version")
        assert versions == [2, 3]
        index_names = _scalar_rows(engine, "SELECT name FROM sqlite_master WHERE type='index'")
        assert "idx_blocker_id" in index_names
        assert "idx_blocked_id" in index_names
        assert "idx_unique_dependency" in index_names
        engine.dispose()


def test_run_migrations_upgrades_legacy_database_without_long_description():
    """A pre-migration database (old todo shape) gets migration 1 applied and recorded."""
    with tempfile.TemporaryDirectory() as temp_dir:
        engine = create_engine(f"sqlite:///{temp_dir}/legacy.db")
        with Session(engine) as session:
            session.exec(
                todo_mcp.text(
                    "CREATE TABLE todo (id INTEGER PRIMARY KEY, description TEXT NOT NULL, status TEXT NOT NULL,"
                    " priority TEXT NOT NULL, due_date TEXT, tags TEXT, created_at TEXT, updated_at TEXT)"
                )
            )
            session.commit()
        todo_mcp.run_migrations(engine)
        versions = _scalar_rows(engine, "SELECT version FROM schema_version ORDER BY version")
        assert versions == [1, 2, 3]
        with Session(engine) as session:
            todo_columns = [row[1] for row in session.exec(todo_mcp.text("PRAGMA table_info(todo)")).all()]
        assert "long_description" in todo_columns
        engine.dispose()


def test_run_migrations_fresh_database_creates_dependency_indexes():
    """Migration 3's unique pair index exists after a fresh run."""
    with tempfile.TemporaryDirectory() as temp_dir:
        engine = create_engine(f"sqlite:///{temp_dir}/fresh.db")
        todo_mcp.run_migrations(engine)
        with Session(engine) as session:
            index_names = [
                row[0] for row in session.exec(todo_mcp.text("SELECT name FROM sqlite_master WHERE type='index'")).all()
            ]
        assert "idx_unique_dependency" in index_names
        assert "idx_blocker_id" in index_names
        assert "idx_blocked_id" in index_names
        engine.dispose()


def test_run_migrations_is_idempotent():
    """Re-running migrations on an up-to-date database inserts no duplicate versions."""
    with tempfile.TemporaryDirectory() as temp_dir:
        engine = create_engine(f"sqlite:///{temp_dir}/fresh.db")
        todo_mcp.run_migrations(engine)
        todo_mcp.run_migrations(engine)
        versions = _scalar_rows(engine, "SELECT version FROM schema_version ORDER BY version")
        assert versions == [2, 3]
        engine.dispose()


def test_run_migrations_reapplies_only_missing_versions():
    """A database missing the version-3 record gets migration 3 reapplied, nothing else."""
    with tempfile.TemporaryDirectory() as temp_dir:
        engine = create_engine(f"sqlite:///{temp_dir}/fresh.db")
        todo_mcp.run_migrations(engine)
        with Session(engine) as session:
            session.exec(todo_mcp.text("DELETE FROM schema_version WHERE version = 3"))
            session.commit()
        todo_mcp.run_migrations(engine)
        versions = _scalar_rows(engine, "SELECT version FROM schema_version ORDER BY version")
        assert versions == [2, 3]  # migration 1 and 2 are NOT re-recorded
        engine.dispose()


# ---------------------------------------------------------------------------
# get_ready_items: ordering and blocked_by shape
# ---------------------------------------------------------------------------


def test_get_ready_items_orders_by_priority_then_due_date(temp_db):
    """Ready items sort by priority rank, then due date; undated last per priority."""
    add_item(description="high overdue", priority="high", due_date_str=(date.today() - timedelta(days=1)).isoformat())
    add_item(description="high future", priority="high", due_date_str=(date.today() + timedelta(days=7)).isoformat())
    add_item(description="medium undated", priority="medium")
    add_item(description="low future", priority="low", due_date_str=(date.today() + timedelta(days=30)).isoformat())
    add_item(description="low undated", priority="low")

    result = get_ready_items()

    assert [item["description"] for item in result["ready"]] == [
        "high overdue",
        "high future",
        "medium undated",
        "low future",
        "low undated",
    ]
    assert result["summary"] == {"ready_count": 5, "blocked_count": 0}


def test_get_ready_items_reports_blockers_with_shape(temp_db):
    """Blocked items carry the exact blocked_by payload and are excluded from ready."""
    add_item(description="blocker task", priority="high")
    add_item(description="waiting task", priority="low")
    add_dependency(blocker_id=1, blocked_id=2)

    result = get_ready_items()

    assert [item["description"] for item in result["ready"]] == ["blocker task"]
    assert len(result["blocked"]) == 1
    blocked = result["blocked"][0]
    assert blocked["description"] == "waiting task"
    assert blocked["blocked_by"] == [{"id": 1, "description": "blocker task", "status": Status.OPEN}]
    assert result["summary"] == {"ready_count": 1, "blocked_count": 1}


# ---------------------------------------------------------------------------
# list_items: every documented sort field in both directions
# ---------------------------------------------------------------------------


@pytest.fixture
def sort_fixtures(temp_db):
    """Five items with distinct values on every sortable field."""
    created = {}
    specs = [
        ("alpha task", "high", "2026-03-01", Status.IN_PROGRESS),
        ("beta task", "low", "2026-01-15", Status.OPEN),
        ("gamma task", "medium", "2026-06-30", Status.DONE),
        ("delta task", "medium", None, Status.CANCELLED),
        ("epsilon task", "high", "2026-02-10", Status.OPEN),
    ]
    for i, (description, priority, due, status) in enumerate(specs):
        result = add_item(description=description, priority=priority, due_date_str=due)
        item_id = result["id"]
        created[description] = item_id
        with Session(temp_db) as session:  # distinct created_at per item
            todo = session.get(todo_mcp.Todo, item_id)
            todo.created_at = datetime(2026, 1, 1, 0, i, 0)
            todo.updated_at = datetime(2026, 2, 1, 0, i, 0)
            session.add(todo)
            session.commit()
        update_item(item_id=item_id, status=status.value)
    return created


SORTED_BY_PRIORITY = ["high", "high", "medium", "medium", "low"]


def test_list_items_sorts_priority_asc_and_desc(sort_fixtures):
    asc = list_items(show_all_statuses=True, sort_by="priority")["items"]
    assert [item["priority"] for item in asc] == SORTED_BY_PRIORITY
    desc = list_items(show_all_statuses=True, sort_by="-priority")["items"]
    assert [item["priority"] for item in desc] == list(reversed(SORTED_BY_PRIORITY))


def test_list_items_sorts_created_at_and_updated_at_asc_and_desc(sort_fixtures):
    ids = sort_fixtures
    order = [ids["alpha task"], ids["beta task"], ids["gamma task"], ids["delta task"], ids["epsilon task"]]
    for field in ("created_at", "updated_at"):
        asc = list_items(show_all_statuses=True, sort_by=field)["items"]
        assert [item["id"] for item in asc] == order, field
        desc = list_items(show_all_statuses=True, sort_by=f"-{field}")["items"]
        assert [item["id"] for item in desc] == list(reversed(order)), field


def test_list_items_sorts_status_asc_and_desc(sort_fixtures):
    asc = list_items(show_all_statuses=True, sort_by="status")["items"]
    assert [item["status"] for item in asc] == sorted(["in_progress", "open", "done", "cancelled", "open"])
    desc = list_items(show_all_statuses=True, sort_by="-status")["items"]
    assert [item["status"] for item in desc] == sorted(
        ["in_progress", "open", "done", "cancelled", "open"], reverse=True
    )


def test_list_items_sorts_description_asc_and_desc(sort_fixtures):
    names = ["alpha task", "beta task", "delta task", "epsilon task", "gamma task"]  # lexical
    ids = sort_fixtures
    asc = list_items(show_all_statuses=True, sort_by="description")["items"]
    assert [item["id"] for item in asc] == [ids[n] for n in names]
    desc = list_items(show_all_statuses=True, sort_by="-description")["items"]
    assert [item["id"] for item in desc] == [ids[n] for n in reversed(names)]


def test_list_items_sorts_due_date_with_undated_last_in_both_directions(sort_fixtures):
    """Dated items order by date; undated items stay last in asc AND desc."""
    ids = sort_fixtures
    dated_asc = [ids["beta task"], ids["epsilon task"], ids["alpha task"], ids["gamma task"]]  # Jan, Feb, Mar, Jun
    asc = list_items(show_all_statuses=True, sort_by="due_date")["items"]
    assert [item["id"] for item in asc if item["due_date"]] == dated_asc
    assert asc[-1]["due_date"] is None  # undated last

    dated_desc = [ids["gamma task"], ids["alpha task"], ids["epsilon task"], ids["beta task"]]
    desc = list_items(show_all_statuses=True, sort_by="-due_date")["items"]
    assert [item["id"] for item in desc if item["due_date"]] == dated_desc
    assert desc[-1]["due_date"] is None  # undated still last when descending


def test_list_items_sorts_id_asc_and_desc(sort_fixtures):
    ids = list(sort_fixtures.values())
    asc = list_items(show_all_statuses=True, sort_by="id")["items"]
    assert [item["id"] for item in asc] == ids
    desc = list_items(show_all_statuses=True, sort_by="-id")["items"]
    assert [item["id"] for item in desc] == list(reversed(ids))


# ---------------------------------------------------------------------------
# add_item / update_item: input handling branches
# ---------------------------------------------------------------------------


def test_add_item_rejects_empty_description(temp_db):
    assert add_item(description="   ") == {"error": "Description cannot be empty."}


def test_add_item_rejects_invalid_due_date(temp_db):
    result = add_item(description="dated", due_date_str="not-a-date")
    assert result["error"].startswith("Invalid date format for due date: 'not-a-date'")


def test_add_item_rejects_invalid_priority_with_error_dict(temp_db):
    result = add_item(description="x", priority="bogus")
    assert set(result) == {"error"}
    assert "bogus" in result["error"]


def test_add_item_stamps_created_at_and_updated_at(temp_db):
    result = add_item(description="stamped")
    assert result["created_at"] is not None
    assert result["updated_at"] is not None
    datetime.fromisoformat(result["created_at"])
    datetime.fromisoformat(result["updated_at"])


def test_update_item_with_no_fields_reports_no_changes(temp_db):
    add_item(description="stable task", priority="low")
    result = update_item(item_id=1)
    assert result["message"] == "No changes specified for the item."
    assert result["item"]["description"] == "stable task"
    assert result["item"]["priority"] == Priority.LOW


def test_update_item_none_strings_clear_fields(temp_db):
    add_item(
        description="task with extras",
        long_description="long text",
        tags="tag1, tag2",
        due_date_str="2026-05-05",
    )
    result = update_item(item_id=1, long_description="none", tags="None", due_date_str="NONE")
    assert result["long_description"] is None
    assert result["tags"] is None
    assert result["due_date"] is None


def test_update_item_rejects_empty_description(temp_db):
    add_item(description="keep me")
    assert update_item(item_id=1, description="  ") == {"error": "Description cannot be empty."}


def test_update_item_rejects_invalid_due_date(temp_db):
    add_item(description="keep me")
    result = update_item(item_id=1, due_date_str="05/05/2026")
    assert result["error"].startswith("Invalid date format for due date: '05/05/2026'")


# ---------------------------------------------------------------------------
# remove_item: not-found and exact message
# ---------------------------------------------------------------------------


def test_remove_item_reports_missing_id(temp_db):
    assert remove_item(item_id=999) == {"error": "Todo item with ID 999 not found."}


def test_remove_item_message_names_the_removed_description(temp_db):
    add_item(description="doomed task")
    result = remove_item(item_id=1)
    assert result["message"] == "Removed todo item #1: 'doomed task'"
    assert result["status"] == "removed"


# ---------------------------------------------------------------------------
# Dependency tools: response shapes, exact-edge removal, traversal
# ---------------------------------------------------------------------------


def test_add_dependency_response_shape(temp_db):
    add_item(description="blocker")
    add_item(description="blocked")
    result = add_dependency(blocker_id=1, blocked_id=2)
    assert result["message"] == "Created dependency: #1 'blocker' blocks #2 'blocked'"
    dep = result["dependency"]
    assert dep["blocker_id"] == 1
    assert dep["blocked_id"] == 2
    assert dep["blocker_description"] == "blocker"
    assert dep["blocked_description"] == "blocked"


def test_list_dependencies_for_item_shape(temp_db):
    add_item(description="parent task", priority="high")
    add_item(description="child task", priority="low")
    add_dependency(blocker_id=1, blocked_id=2)

    result = list_dependencies(item_id=2)
    assert result["item"] == {"id": 2, "description": "child task", "status": Status.OPEN, "priority": Priority.LOW}
    assert result["blocked_by"] == [
        {"id": 1, "description": "parent task", "status": Status.OPEN, "priority": Priority.HIGH}
    ]
    assert result["blocks"] == []


def test_list_dependencies_all_shape(temp_db):
    add_item(description="parent task")
    add_item(description="child task")
    add_dependency(blocker_id=1, blocked_id=2)

    result = list_dependencies()
    assert len(result["dependencies"]) == 1
    dep = result["dependencies"][0]
    assert dep["blocker"] == {"id": 1, "description": "parent task", "status": Status.OPEN}
    assert dep["blocked"] == {"id": 2, "description": "child task", "status": Status.OPEN}
    assert set(dep) == {"id", "blocker", "blocked", "created_at"}
    assert dep["id"] == 1
    datetime.fromisoformat(dep["created_at"])


def test_list_dependencies_blocks_direction_exact_shape(temp_db):
    add_item(description="blocked item")
    add_item(description="upstream blocker")
    add_item(description="downstream dependent")
    add_dependency(blocker_id=2, blocked_id=1)  # 2 blocks 1
    add_dependency(blocker_id=1, blocked_id=3)  # 1 blocks 3

    result = list_dependencies(item_id=1)
    assert result["blocked_by"] == [
        {"id": 2, "description": "upstream blocker", "status": Status.OPEN, "priority": Priority.MEDIUM}
    ]
    assert result["blocks"] == [
        {"id": 3, "description": "downstream dependent", "status": Status.OPEN, "priority": Priority.MEDIUM}
    ]


def test_remove_dependency_removes_only_the_exact_edge(temp_db):
    for description in ("one", "two", "three", "four", "five"):
        add_item(description=description)
    # Create an edge sharing the blocker FIRST: under an OR-combined where clause
    # (mutant for the & conjunction), the row matching the blocker arm alone (1->5)
    # comes back from .first() before the exact edge (1->3), so over-deletion is
    # observable through item 5's blocked_by list.
    add_dependency(blocker_id=1, blocked_id=5)
    add_dependency(blocker_id=1, blocked_id=3)
    add_dependency(blocker_id=2, blocked_id=3)

    result = remove_dependency(blocker_id=1, blocked_id=3)
    assert result["status"] == "removed"

    remaining = list_dependencies(item_id=3)["blocked_by"]
    assert [dep["id"] for dep in remaining] == [2]  # the 1->3 edge is gone, 2->3 stays
    still_blocked = list_dependencies(item_id=5)["blocked_by"]
    assert [dep["id"] for dep in still_blocked] == [1]  # the 1->5 edge is untouched


def test_get_dependency_chain_traverses_both_directions(temp_db):
    for name in ("root", "middle", "leaf"):
        add_item(description=name, priority="high")
    add_dependency(blocker_id=1, blocked_id=2)
    add_dependency(blocker_id=2, blocked_id=3)

    both = get_dependency_chain(item_id=2)
    assert both["item"] == {"id": 2, "description": "middle", "status": Status.OPEN, "priority": Priority.HIGH}
    assert both["upstream"] == [
        {"id": 1, "description": "root", "status": Status.OPEN, "priority": Priority.HIGH, "blockers": []}
    ]
    assert both["downstream"] == [
        {"id": 3, "description": "leaf", "status": Status.OPEN, "priority": Priority.HIGH, "blocked": []}
    ]

    up_only = get_dependency_chain(item_id=2, direction="upstream")
    assert up_only["upstream"][0]["id"] == 1
    assert "downstream" not in up_only


def test_get_dependency_chain_rejects_unknown_direction(temp_db):
    add_item(description="solo")
    assert get_dependency_chain(item_id=1, direction="sideways") == {
        "error": "Direction must be 'upstream', 'downstream', or 'both'"
    }


def test_add_dependency_success_response_shape(temp_db):
    add_item(description="blocker")
    add_item(description="blocked")
    result = add_dependency(blocker_id=1, blocked_id=2)
    assert "error" not in result
    assert set(result) == {"message", "dependency"}
    dependency = result["dependency"]
    assert set(dependency) == {
        "id",
        "blocker_id",
        "blocker_description",
        "blocked_id",
        "blocked_description",
        "created_at",
    }
    assert dependency["id"] == 1
    datetime.fromisoformat(dependency["created_at"])  # stamped, not None


def test_add_dependency_cycle_walk_continues_past_visited_nodes(temp_db):
    # The cycle check for add(A blocks B) walks downstream from B seeking A.
    # Reconvergent DAG: 2 blocks 3 and 4; both 3 and 4 block 5; 5 blocks 1. Adding
    # 1 blocks 2 is a cycle (2 blocks 5 blocks 1 transitively), but the walk
    # re-encounters the already-visited node 5 (queued once under 3 and once under 4)
    # before it reaches 1 — a break-instead-of-continue mutant would miss the cycle.
    for description in ("one", "two", "three", "four", "five"):
        add_item(description=description)
    assert "error" not in add_dependency(blocker_id=2, blocked_id=3)
    assert "error" not in add_dependency(blocker_id=2, blocked_id=4)
    assert "error" not in add_dependency(blocker_id=3, blocked_id=5)
    assert "error" not in add_dependency(blocker_id=4, blocked_id=5)
    assert "error" not in add_dependency(blocker_id=5, blocked_id=1)

    result = add_dependency(blocker_id=1, blocked_id=2)
    assert "circular dependency" in result.get("error", "")


def test_add_dependency_rejects_the_reverse_edge_of_an_existing_dependency(temp_db):
    # The cycle check is bidirectional in effect: once 1 blocks 2, adding 2 blocks 1
    # is rejected because the walk from the new blocked item (1) reaches the new
    # blocker (2) through the existing edge.
    for description in ("one", "two"):
        add_item(description=description)
    assert "error" not in add_dependency(blocker_id=1, blocked_id=2)
    result = add_dependency(blocker_id=2, blocked_id=1)
    assert "circular dependency" in result.get("error", "")


def test_get_dependency_chain_upstream_skips_visited_without_truncating(temp_db):
    # Blockers of 4 are [1, 2, 3]; 2 is also reachable (and listed) under 1, so the
    # traversal must skip it WITHOUT dropping the later sibling 3.
    for description in ("one", "two", "three", "four"):
        add_item(description=description)
    add_dependency(blocker_id=2, blocked_id=1)
    add_dependency(blocker_id=1, blocked_id=4)
    add_dependency(blocker_id=2, blocked_id=4)
    add_dependency(blocker_id=3, blocked_id=4)

    result = get_dependency_chain(item_id=4, direction="upstream")
    assert [entry["id"] for entry in result["upstream"]] == [1, 3]
    assert result["upstream"][0]["blockers"] == [
        {"id": 2, "description": "two", "status": Status.OPEN, "priority": Priority.MEDIUM, "blockers": []}
    ]


def test_get_dependency_chain_downstream_skips_visited_without_truncating(temp_db):
    # Mirror of the upstream shape: blocked-of-4 order is [1, 2, 3], 2 is already
    # listed under 1, and 3 must still appear afterwards.
    for description in ("one", "two", "three", "four"):
        add_item(description=description)
    add_dependency(blocker_id=4, blocked_id=1)
    add_dependency(blocker_id=4, blocked_id=2)
    add_dependency(blocker_id=4, blocked_id=3)
    add_dependency(blocker_id=1, blocked_id=2)

    result = get_dependency_chain(item_id=4, direction="downstream")
    assert [entry["id"] for entry in result["downstream"]] == [1, 3]
    assert result["downstream"][0]["blocked"] == [
        {"id": 2, "description": "two", "status": Status.OPEN, "priority": Priority.MEDIUM, "blocked": []}
    ]


def test_update_item_invalid_status_and_priority_exact_errors(temp_db):
    add_item(description="target")
    result = update_item(item_id=1, status="bogus")
    assert set(result) == {"error"}
    assert result["error"].startswith("Invalid status: 'bogus'.")
    assert "Valid:" in result["error"]

    result = update_item(item_id=1, priority="bogus")
    assert set(result) == {"error"}
    assert result["error"].startswith("Invalid priority: 'bogus'.")
    assert "Valid:" in result["error"]


def test_list_parsers_error_messages_name_the_value():
    with pytest.raises(ValueError, match="Invalid status"):
        parse_status_list("bogus")
    with pytest.raises(ValueError, match="Invalid priority"):
        parse_priority_list("bogus")


def test_get_dependency_chain_reports_missing_item(temp_db):
    assert "not found" in get_dependency_chain(item_id=4242)["error"]


# ---------------------------------------------------------------------------
# Parsers: validation, passthrough, suggestions, list forms
# ---------------------------------------------------------------------------


def test_parse_priority_passthrough_and_error():
    assert parse_priority(None) is None
    assert parse_priority(Priority.HIGH) == Priority.HIGH
    assert parse_priority("high") == Priority.HIGH
    assert parse_priority("HIGH") == Priority.HIGH
    assert parse_priority(" high ") == Priority.HIGH
    assert parse_priority("High") == Priority.HIGH  # name form
    with pytest.raises(ValueError) as excinfo:
        parse_priority("hig")
    assert "Did you mean 'high'?" in str(excinfo.value)


def test_parse_status_passthrough_and_error():
    assert parse_status(None) is None
    assert parse_status(Status.DONE) == Status.DONE
    assert parse_status("in_progress") == Status.IN_PROGRESS
    assert parse_status("IN_PROGRESS") == Status.IN_PROGRESS
    assert parse_status("open ") == Status.OPEN
    with pytest.raises(ValueError) as excinfo:
        parse_status("inprogress")
    assert "Did you mean 'in_progress'?" in str(excinfo.value)


def test_parse_priority_list_forms():
    assert parse_priority_list(None) is None
    assert parse_priority_list("low") == [Priority.LOW]
    assert parse_priority_list(Priority.LOW) == [Priority.LOW]
    assert parse_priority_list(["high", "low"]) == [Priority.HIGH, Priority.LOW]
    with pytest.raises(ValueError):
        parse_priority_list(["high", "bogus"])


def test_parse_status_list_forms():
    assert parse_status_list(None) is None
    assert parse_status_list("done") == [Status.DONE]
    assert parse_status_list(Status.OPEN) == [Status.OPEN]
    assert parse_status_list(["open", "done"]) == [Status.OPEN, Status.DONE]
    with pytest.raises(ValueError):
        parse_status_list(["open", "closed"])


def test_suggest_correction_matches_and_misses():
    assert suggest_correction("hig", ["high", "low"]) == "Did you mean 'high'?"
    assert suggest_correction("zzzzzz", ["high", "low"]) == ""


# ---------------------------------------------------------------------------
# todo_to_dict: datetime/date serialization
# ---------------------------------------------------------------------------


def test_todo_to_dict_serializes_datetimes_and_dates():
    todo = todo_mcp.Todo(
        description="timestamps",
        created_at=datetime(2026, 9, 8, 10, 30, 0),
        updated_at=datetime(2026, 9, 8, 11, 0, 0),
        due_date=date(2026, 12, 25),
    )
    as_dict = todo_to_dict(todo)
    assert as_dict["created_at"] == "2026-09-08T10:30:00"
    assert as_dict["updated_at"] == "2026-09-08T11:00:00"
    assert as_dict["due_date"] == "2026-12-25"


def test_todo_to_dict_leaves_plain_strings_untouched():
    todo = todo_mcp.Todo(description="strings", created_at="already-a-string", due_date="2026-01-01")
    as_dict = todo_to_dict(todo)
    assert as_dict["created_at"] == "already-a-string"
    assert as_dict["due_date"] == "2026-01-01"


# ---------------------------------------------------------------------------
# CLI parsing and database path resolution
# ---------------------------------------------------------------------------


def test_parse_cli_args_reads_project_dir(monkeypatch):
    monkeypatch.setattr(sys, "argv", ["todo_mcp.py", "--project-dir", "/home/user/some-project"])
    args = todo_mcp.parse_cli_args()
    assert args.project_dir == "/home/user/some-project"


def test_parse_cli_args_defaults_to_none(monkeypatch):
    monkeypatch.setattr(sys, "argv", ["todo_mcp.py"])
    args = todo_mcp.parse_cli_args()
    assert args.project_dir is None


def test_get_cli_args_is_cached(monkeypatch):
    todo_mcp.get_cli_args.cache_clear()
    monkeypatch.setattr(sys, "argv", ["todo_mcp.py", "--project-dir", "/home/user/cached-project"])
    assert todo_mcp.get_cli_args().project_dir == "/home/user/cached-project"
    monkeypatch.setattr(sys, "argv", ["todo_mcp.py", "--project-dir", "/home/user/other-project"])
    assert todo_mcp.get_cli_args().project_dir == "/home/user/cached-project"  # cached, not re-parsed
    todo_mcp.get_cli_args.cache_clear()


def test_resolve_database_path_explicit_directory(tmp_path):
    namespace = argparse_namespace(project_dir=str(tmp_path))
    assert resolve_database_path(namespace) == tmp_path / "todo.db"


def test_resolve_database_path_rejects_missing_directory(tmp_path, caplog):
    import logging

    namespace = argparse_namespace(project_dir=str(tmp_path / "nope"))
    with pytest.raises(SystemExit) as excinfo:
        resolve_database_path(namespace)
    assert excinfo.value.code == 1  # error path must exit non-zero
    error_messages = [record.getMessage() for record in caplog.records if record.levelno >= logging.ERROR]
    expected = f"Provided project directory does not exist or is not a directory: {(tmp_path / 'nope').resolve()}"
    assert error_messages == [expected]


def test_resolve_database_path_falls_back_to_parent_of_script(caplog):
    import logging

    namespace = argparse_namespace(project_dir=None)
    with caplog.at_level(logging.WARNING):
        result = resolve_database_path(namespace)
    expected = pathlib.Path(todo_mcp.__file__).resolve().parent.parent / "todo.db"
    assert result == expected
    warning_messages = [record.getMessage() for record in caplog.records if record.levelno >= logging.WARNING]
    assert warning_messages == [
        "--project-dir not specified. Defaulting todo.db to script's"
        " directory parent. Use --project-dir for explicit control."
    ]


def test_get_engine_builds_sqlite_engine_for_project_dir(tmp_path, monkeypatch):
    monkeypatch.setattr(todo_mcp, "engine", None)
    todo_mcp.get_cli_args.cache_clear()
    monkeypatch.setattr(sys, "argv", ["todo_mcp.py", "--project-dir", str(tmp_path)])
    try:
        engine = todo_mcp.get_engine()
        assert str(engine.url) == f"sqlite:///{tmp_path / 'todo.db'}"
        engine.dispose()
    finally:
        todo_mcp.get_cli_args.cache_clear()


def argparse_namespace(project_dir):
    """Minimal stand-in for the CLI namespace used by resolve_database_path."""
    import argparse

    return argparse.Namespace(project_dir=project_dir)


# ---------------------------------------------------------------------------
# Round 2: mutants that survived the first hardening pass
# ---------------------------------------------------------------------------


def test_list_items_default_excludes_completed_items(temp_db):
    """The show_all_statuses default is False: completed items stay off the default board."""
    add_item(description="open work")
    done_id = add_item(description="finished work")["id"]
    update_item(item_id=done_id, status="done")

    default_view = list_items()["items"]
    assert [item["description"] for item in default_view] == ["open work"]

    everything = list_items(show_all_statuses=True)["items"]
    assert {item["description"] for item in everything} == {"open work", "finished work"}


def test_list_items_invalid_status_filter_returns_exact_error(temp_db):
    add_item(description="any")
    result = list_items(status_filter="bogus")
    assert set(result) == {"error"}
    assert "bogus" in result["error"]
    assert "open" in result["error"]  # valid values are listed in the message


def test_list_items_invalid_priority_filter_returns_exact_error(temp_db):
    add_item(description="any")
    result = list_items(priority_filter="bogus")
    assert set(result) == {"error"}
    assert "bogus" in result["error"]
    assert "high" in result["error"]


def test_list_items_invalid_tag_filter_returns_exact_error(temp_db):
    add_item(description="any")
    result = list_items(tag_filter=123)  # type: ignore[arg-type]
    assert set(result) == {"error"}
    assert "tag_filter" in result["error"]


def test_update_item_invalid_status_returns_exact_error(temp_db):
    item_id = add_item(description="x")["id"]
    result = update_item(item_id=item_id, status="bogus")
    assert set(result) == {"error"}
    assert "bogus" in result["error"]


def test_update_item_sets_and_clears_long_description(temp_db):
    item_id = add_item(description="x")["id"]
    result = update_item(item_id=item_id, long_description="detailed notes")
    assert result["long_description"] == "detailed notes"
    result = update_item(item_id=item_id, long_description="none")
    assert result["long_description"] is None


def test_tag_filter_excludes_untagged_items(temp_db):
    """An item with no tags never matches a tag filter (issue #8 semantics)."""
    add_item(description="tagged", tags="database")
    add_item(description="untagged")

    result = list_items(tag_filter="database")

    assert [item["description"] for item in result["items"]] == ["tagged"]


def test_due_date_sort_pins_ties_and_undated_in_both_directions(temp_db):
    """sort_by='due_date' is a total order: created_at breaks ties, undated last."""
    ids = {}
    for description, due, created in (
        ("dated early", "2026-01-01", 12),
        ("tie first", "2026-05-01", 10),
        ("tie second", "2026-05-01", 11),
        ("undated", None, 9),
    ):
        item_id = add_item(description=description, due_date_str=due)["id"]
        ids[description] = item_id
        with Session(temp_db) as session:
            todo = session.get(todo_mcp.Todo, item_id)
            todo.created_at = datetime(2026, 1, 1, 0, created, 0)
            session.add(todo)
            session.commit()

    asc = list_items(show_all_statuses=True, sort_by="due_date")["items"]
    assert [item["description"] for item in asc] == ["dated early", "tie first", "tie second", "undated"]

    desc = list_items(show_all_statuses=True, sort_by="-due_date")["items"]
    assert [item["description"] for item in desc] == ["tie first", "tie second", "dated early", "undated"]


def test_remove_item_returns_exact_response(temp_db):
    item_id = add_item(description="to remove")["id"]
    result = remove_item(item_id=item_id)
    assert result == {
        "message": f"Removed todo item #{item_id}: 'to remove'",
        "id": item_id,
        "status": "removed",
    }


def test_add_dependency_returns_parseable_created_at(temp_db):
    add_item(description="blocker")
    add_item(description="blocked")
    dep = add_dependency(blocker_id=1, blocked_id=2)["dependency"]
    assert isinstance(dep["created_at"], str)
    datetime.fromisoformat(dep["created_at"])  # parses as ISO timestamp


def test_add_dependency_rejects_self_blockage_with_exact_message(temp_db):
    add_item(description="solo")
    result = add_dependency(blocker_id=1, blocked_id=1)
    assert result == {"error": "A todo item cannot block itself."}


def test_list_dependencies_skips_dangling_rows(temp_db):
    """A dependency row pointing at a deleted item is skipped, not crashed on."""
    add_item(description="real")
    with Session(temp_db) as session:
        session.exec(
            todo_mcp.text(
                "INSERT INTO tododependency (blocker_id, blocked_id, created_at) VALUES (1, 999, '2026-01-01 00:00:00')"
            )
        )
        session.commit()

    result = list_dependencies()

    assert result["dependencies"] == []


def test_dependency_chain_diamond_visits_each_item_once(temp_db):
    """Traversal marks visited nodes: a reconvergent graph lists each item exactly once."""
    for name in ("top", "left", "right", "bottom", "extra"):
        add_item(description=name)
    # top blocks left and right; both left and right block bottom; extra blocks right.
    add_dependency(blocker_id=1, blocked_id=2)
    add_dependency(blocker_id=1, blocked_id=3)
    add_dependency(blocker_id=2, blocked_id=4)
    add_dependency(blocker_id=3, blocked_id=4)
    add_dependency(blocker_id=5, blocked_id=3)

    def walk(nodes, nested_key):
        found = []
        for node in nodes:
            found.append(node["id"])
            found.extend(walk(node[nested_key], nested_key))
        return found

    result = get_dependency_chain(item_id=1)
    assert sorted(walk(result["downstream"], "blocked")) == [2, 3, 4]

    result = get_dependency_chain(item_id=4)
    assert sorted(walk(result["upstream"], "blockers")) == [1, 2, 3, 5]


def test_migrations_on_current_database_run_silently(caplog):
    """Re-running migrations on a fully-migrated DB re-runs nothing and logs no warnings."""
    import logging

    with tempfile.TemporaryDirectory() as temp_dir:
        engine = create_engine(f"sqlite:///{temp_dir}/fresh.db")
        todo_mcp.run_migrations(engine)
        caplog.clear()  # discard the first run's expected probe warnings
        with caplog.at_level(logging.WARNING):
            todo_mcp.run_migrations(engine)
        warnings = [record for record in caplog.records if record.levelno >= logging.WARNING]
        assert warnings == []
        assert _scalar_rows(engine, "SELECT version FROM schema_version ORDER BY version") == [2, 3]
        engine.dispose()


def test_fresh_migration_run_records_versions_without_errors(caplog):
    """A fresh run logs only the expected migration-1 probe warning; versions still recorded."""
    import logging

    with tempfile.TemporaryDirectory() as temp_dir:
        engine = create_engine(f"sqlite:///{temp_dir}/fresh.db")
        with caplog.at_level(logging.WARNING):
            todo_mcp.run_migrations(engine)
        errors = [record for record in caplog.records if record.levelno >= logging.ERROR]
        assert errors == []
        assert _scalar_rows(engine, "SELECT version FROM schema_version ORDER BY version") == [2, 3]
        engine.dispose()
