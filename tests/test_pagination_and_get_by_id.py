import pytest
from sqlmodel import SQLModel, create_engine
from todo_mcp import add_item, list_items, get_item_by_id

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
def sample_todos(temp_db):
    # Add multiple sample todo items for testing pagination
    todo_ids = []
    for i in range(15):
        result = add_item(
            description=f"Test item {i + 1}",
            priority="high" if i % 3 == 0 else "medium" if i % 3 == 1 else "low",
            tags=f"tag{i % 4}",
        )
        todo_ids.append(result["id"])
    return todo_ids


def test_get_item_by_id_success(temp_db, sample_todos):
    # Should retrieve a specific item by ID
    item_id = sample_todos[0]
    result = get_item_by_id(item_id=item_id)

    assert "error" not in result
    assert result["id"] == item_id
    assert result["description"] == "Test item 1"
    assert result["priority"] == "high"


def test_get_item_by_id_not_found(temp_db):
    # Should return error for non-existent item
    result = get_item_by_id(item_id=9999)

    assert "error" in result
    assert "not found" in result["error"]


def test_list_items_pagination_basic(temp_db, sample_todos):
    # Should paginate results correctly
    result = list_items(limit=5)

    assert "items" in result
    assert "total_count" in result
    assert len(result["items"]) == 5
    assert result["total_count"] == 15


def test_list_items_pagination_with_offset(temp_db, sample_todos):
    # Should paginate with offset correctly
    result = list_items(limit=5, offset=10)

    assert "items" in result
    assert "total_count" in result
    assert len(result["items"]) == 5
    assert result["total_count"] == 15


def test_list_items_pagination_last_page(temp_db, sample_todos):
    # Should handle last page with fewer items
    result = list_items(limit=10, offset=10)

    assert "items" in result
    assert "total_count" in result
    assert len(result["items"]) == 5  # Only 5 items left on last page
    assert result["total_count"] == 15


def test_list_items_no_pagination_no_total_count(temp_db, sample_todos):
    # Should not include total_count when pagination not used
    result = list_items()

    assert "items" in result
    assert "total_count" not in result  # Should not include when no pagination
    assert len(result["items"]) == 15


def test_list_items_pagination_with_filters(temp_db, sample_todos):
    # Should paginate filtered results correctly
    result = list_items(priority_filter="high", limit=2)

    assert "items" in result
    assert "total_count" in result
    assert len(result["items"]) == 2
    # Should have 5 high priority items (every 3rd item)
    assert result["total_count"] == 5


def test_list_items_pagination_empty_results(temp_db, sample_todos):
    # Should handle pagination when offset exceeds results
    result = list_items(limit=5, offset=20)

    assert "items" in result
    assert "total_count" in result
    assert len(result["items"]) == 0
    assert result["total_count"] == 15


def test_list_items_limit_only(temp_db, sample_todos):
    # Should work with just limit (no offset)
    result = list_items(limit=3)

    assert "items" in result
    assert "total_count" in result
    assert len(result["items"]) == 3
    assert result["total_count"] == 15


def test_list_items_offset_only(temp_db, sample_todos):
    # Should work with just offset (no limit)
    result = list_items(offset=10)

    assert "items" in result
    assert "total_count" in result
    assert len(result["items"]) == 5  # Remaining items after offset 10
    assert result["total_count"] == 15


def test_pagination_with_priority_sorting(temp_db, sample_todos):
    # Should paginate correctly with priority sorting
    result = list_items(sort_by="priority", limit=5)

    assert "items" in result
    assert "total_count" in result
    assert len(result["items"]) == 5
    assert result["total_count"] == 15

    # Check that items are sorted by priority (high first)
    priorities = [item["priority"] for item in result["items"]]
    assert priorities[0] == "high"


def test_pagination_with_tag_filter_and_sorting(temp_db, sample_todos):
    # Should handle complex filtering, sorting, and pagination together
    result = list_items(tag_filter="tag0", sort_by="-created_at", limit=2)

    assert "items" in result
    assert "total_count" in result
    assert len(result["items"]) <= 2
    # Should have items with tag0 (every 4th item: items 1, 5, 9, 13)
    assert result["total_count"] == 4


def test_get_item_by_id_with_all_fields(temp_db):
    # Test get_item_by_id with item that has all fields populated
    result = add_item(
        description="Comprehensive test item",
        priority="high",
        due_date_str="2024-12-31",
        tags="test,comprehensive,full",
        long_description="This is a detailed long description for testing purposes",
    )
    item_id = result["id"]

    retrieved = get_item_by_id(item_id=item_id)

    assert "error" not in retrieved
    assert retrieved["id"] == item_id
    assert retrieved["description"] == "Comprehensive test item"
    assert retrieved["priority"] == "high"
    assert retrieved["due_date"] == "2024-12-31"
    assert retrieved["tags"] == "test,comprehensive,full"
    assert retrieved["long_description"] == "This is a detailed long description for testing purposes"
    assert retrieved["status"] == "open"
    assert "created_at" in retrieved
    assert "updated_at" in retrieved
