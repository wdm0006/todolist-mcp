"""Tests for list_items text search."""

import pytest
from sqlmodel import SQLModel, create_engine

import todo_mcp


@pytest.fixture
def ids(tmp_path, monkeypatch):
    engine = create_engine(f"sqlite:///{tmp_path / 'todo.db'}")
    SQLModel.metadata.create_all(engine)
    monkeypatch.setattr(todo_mcp, "engine", engine)
    rows = {
        "desc": todo_mcp.add_item("Implement OAuth login", priority="high", tags="backend"),
        "long": todo_mcp.add_item("Auth work", long_description="Use oauth2 flow", priority="low"),
        "tag": todo_mcp.add_item("Rotate keys", tags="Security,OAuth-prep", priority="high"),
        "none": todo_mcp.add_item("Write docs", tags="docs"),
        "pct": todo_mcp.add_item("Reach 100% coverage", tags="a_b"),
        "other": todo_mcp.add_item("Reach 100 coverage", tags="axb"),
    }
    return {k: v["id"] for k, v in rows.items()}


def found(**kw):
    return sorted(i["id"] for i in todo_mcp.list_items(show_all_statuses=True, **kw)["items"])


def test_matches_description_long_description_and_tags(ids):
    assert found(search="OAUTH") == sorted([ids["desc"], ids["long"], ids["tag"]])


def test_long_description_only(ids):
    assert found(search="oauth2") == [ids["long"]]


def test_tags_only(ids):
    assert found(search="security") == [ids["tag"]]


def test_blank_search_is_no_filter(ids):
    everything = found()
    assert found(search="") == everything
    assert found(search="   ") == everything
    assert found(search=None) == everything


def test_percent_and_underscore_are_literal(ids):
    assert found(search="%") == [ids["pct"]]
    assert found(search="a_b") == [ids["pct"]]
    assert found(search="_") == [ids["pct"]]


def test_composes_with_filters(ids):
    assert found(search="oauth", priority_filter="high") == sorted([ids["desc"], ids["tag"]])
    assert found(search="oauth", tag_filter="backend") == [ids["desc"]]
    todo_mcp.update_item(ids["desc"], status="done")
    assert found(search="oauth", status_filter="done") == [ids["desc"]]
    assert todo_mcp.list_items(search="oauth")["items"].__len__() == 2  # default hides done


def test_total_count_and_pagination_after_search(ids):
    res = todo_mcp.list_items(show_all_statuses=True, search="oauth", sort_by="id", limit=2, offset=1)
    assert res["total_count"] == 3
    assert [i["id"] for i in res["items"]] == sorted([ids["desc"], ids["long"], ids["tag"]])[1:3]


def test_sort_by_applies_to_search(ids):
    res = todo_mcp.list_items(show_all_statuses=True, search="oauth", sort_by="-id")
    assert [i["id"] for i in res["items"]] == sorted([ids["desc"], ids["long"], ids["tag"]], reverse=True)
