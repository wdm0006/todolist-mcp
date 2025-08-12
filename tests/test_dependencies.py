#!/usr/bin/env python3
"""Tests for todo dependency functionality."""

import pathlib
import pytest
import sys
import tempfile
from sqlmodel import Session, create_engine
from unittest.mock import patch

# Add the project root to the Python path
project_root = pathlib.Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

import todo_mcp  # noqa: E402


@pytest.fixture
def temp_db():
    """Create a temporary database for testing."""
    with tempfile.TemporaryDirectory() as temp_dir:
        temp_db_path = pathlib.Path(temp_dir) / "test_todo.db"
        temp_engine = create_engine(f"sqlite:///{temp_db_path}")

        # Patch the global engine
        with patch.object(todo_mcp, "engine", temp_engine):
            # Create tables
            todo_mcp.SQLModel.metadata.create_all(temp_engine)
            todo_mcp.run_migrations()
            yield temp_engine


@pytest.fixture
def sample_todos(temp_db):
    """Create sample todo items for testing dependencies."""
    with Session(temp_db) as session:
        todo1 = todo_mcp.Todo(
            description="Setup database schema",
            priority=todo_mcp.Priority.HIGH,
            status=todo_mcp.Status.OPEN,
            tags="backend,setup",
        )
        todo2 = todo_mcp.Todo(
            description="Implement user authentication",
            priority=todo_mcp.Priority.HIGH,
            status=todo_mcp.Status.OPEN,
            tags="backend,auth",
        )
        todo3 = todo_mcp.Todo(
            description="Create login UI",
            priority=todo_mcp.Priority.MEDIUM,
            status=todo_mcp.Status.OPEN,
            tags="frontend,auth",
        )
        todo4 = todo_mcp.Todo(
            description="Write API documentation",
            priority=todo_mcp.Priority.LOW,
            status=todo_mcp.Status.OPEN,
            tags="docs",
        )

        session.add_all([todo1, todo2, todo3, todo4])
        session.commit()
        session.refresh(todo1)
        session.refresh(todo2)
        session.refresh(todo3)
        session.refresh(todo4)

        return {"schema": todo1, "auth": todo2, "ui": todo3, "docs": todo4}


class TestDependencyManagement:
    """Test dependency creation, removal, and listing."""

    def test_add_dependency_success(self, sample_todos):
        """Test successful dependency creation."""
        schema_id = sample_todos["schema"].id
        auth_id = sample_todos["auth"].id

        result = todo_mcp.add_dependency(blocker_id=schema_id, blocked_id=auth_id)

        assert "error" not in result
        assert "message" in result
        assert f"#{schema_id}" in result["message"]
        assert f"#{auth_id}" in result["message"]
        assert result["dependency"]["blocker_id"] == schema_id
        assert result["dependency"]["blocked_id"] == auth_id
        assert "created_at" in result["dependency"]

    def test_add_dependency_self_blocking(self, sample_todos):
        """Test that an item cannot block itself."""
        schema_id = sample_todos["schema"].id

        result = todo_mcp.add_dependency(blocker_id=schema_id, blocked_id=schema_id)

        assert "error" in result
        assert "cannot block itself" in result["error"]

    def test_add_dependency_nonexistent_blocker(self, sample_todos):
        """Test error when blocker doesn't exist."""
        auth_id = sample_todos["auth"].id

        result = todo_mcp.add_dependency(blocker_id=999, blocked_id=auth_id)

        assert "error" in result
        assert "not found" in result["error"]

    def test_add_dependency_nonexistent_blocked(self, sample_todos):
        """Test error when blocked item doesn't exist."""
        schema_id = sample_todos["schema"].id

        result = todo_mcp.add_dependency(blocker_id=schema_id, blocked_id=999)

        assert "error" in result
        assert "not found" in result["error"]

    def test_add_dependency_duplicate(self, sample_todos):
        """Test that duplicate dependencies are not allowed."""
        schema_id = sample_todos["schema"].id
        auth_id = sample_todos["auth"].id

        # Add first dependency
        result1 = todo_mcp.add_dependency(blocker_id=schema_id, blocked_id=auth_id)
        assert "error" not in result1

        # Try to add the same dependency again
        result2 = todo_mcp.add_dependency(blocker_id=schema_id, blocked_id=auth_id)
        assert "error" in result2
        assert "already exists" in result2["error"]

    def test_remove_dependency_success(self, sample_todos):
        """Test successful dependency removal."""
        schema_id = sample_todos["schema"].id
        auth_id = sample_todos["auth"].id

        # First add a dependency
        todo_mcp.add_dependency(blocker_id=schema_id, blocked_id=auth_id)

        # Then remove it
        result = todo_mcp.remove_dependency(blocker_id=schema_id, blocked_id=auth_id)

        assert "error" not in result
        assert "message" in result
        assert "no longer blocks" in result["message"]
        assert result["status"] == "removed"

    def test_remove_dependency_nonexistent(self, sample_todos):
        """Test error when removing non-existent dependency."""
        schema_id = sample_todos["schema"].id
        auth_id = sample_todos["auth"].id

        result = todo_mcp.remove_dependency(blocker_id=schema_id, blocked_id=auth_id)

        assert "error" in result
        assert "No dependency found" in result["error"]


class TestDependencyListing:
    """Test dependency listing and querying functionality."""

    def test_list_dependencies_for_item(self, sample_todos):
        """Test listing dependencies for a specific item."""
        schema_id = sample_todos["schema"].id
        auth_id = sample_todos["auth"].id
        ui_id = sample_todos["ui"].id

        # Create dependencies: schema -> auth -> ui
        todo_mcp.add_dependency(blocker_id=schema_id, blocked_id=auth_id)
        todo_mcp.add_dependency(blocker_id=auth_id, blocked_id=ui_id)

        # Check auth item dependencies
        result = todo_mcp.list_dependencies(item_id=auth_id)

        assert "error" not in result
        assert "item" in result
        assert result["item"]["id"] == auth_id
        assert len(result["blocked_by"]) == 1
        assert result["blocked_by"][0]["id"] == schema_id
        assert len(result["blocks"]) == 1
        assert result["blocks"][0]["id"] == ui_id

    def test_list_dependencies_nonexistent_item(self, sample_todos):
        """Test error when listing dependencies for non-existent item."""
        result = todo_mcp.list_dependencies(item_id=999)

        assert "error" in result
        assert "not found" in result["error"]

    def test_list_all_dependencies(self, sample_todos):
        """Test listing all dependencies in the system."""
        schema_id = sample_todos["schema"].id
        auth_id = sample_todos["auth"].id
        ui_id = sample_todos["ui"].id
        docs_id = sample_todos["docs"].id

        # Create multiple dependencies
        todo_mcp.add_dependency(blocker_id=schema_id, blocked_id=auth_id)
        todo_mcp.add_dependency(blocker_id=auth_id, blocked_id=ui_id)
        todo_mcp.add_dependency(blocker_id=auth_id, blocked_id=docs_id)

        result = todo_mcp.list_dependencies()

        assert "error" not in result
        assert "dependencies" in result
        assert len(result["dependencies"]) == 3

        # Check that all dependencies are represented
        dep_pairs = [(d["blocker"]["id"], d["blocked"]["id"]) for d in result["dependencies"]]
        assert (schema_id, auth_id) in dep_pairs
        assert (auth_id, ui_id) in dep_pairs
        assert (auth_id, docs_id) in dep_pairs


class TestReadyItems:
    """Test the get_ready_items functionality."""

    def test_get_ready_items_no_dependencies(self, sample_todos):
        """Test that all items are ready when there are no dependencies."""
        result = todo_mcp.get_ready_items()

        assert "error" not in result
        assert len(result["ready"]) == 4  # All items should be ready
        assert len(result["blocked"]) == 0
        assert result["summary"]["ready_count"] == 4
        assert result["summary"]["blocked_count"] == 0

    def test_get_ready_items_with_dependencies(self, sample_todos):
        """Test ready items with some dependencies."""
        schema_id = sample_todos["schema"].id
        auth_id = sample_todos["auth"].id
        ui_id = sample_todos["ui"].id

        # Create chain: schema -> auth -> ui
        todo_mcp.add_dependency(blocker_id=schema_id, blocked_id=auth_id)
        todo_mcp.add_dependency(blocker_id=auth_id, blocked_id=ui_id)

        result = todo_mcp.get_ready_items()

        assert "error" not in result
        # Only schema and docs should be ready (no blockers)
        ready_ids = [item["id"] for item in result["ready"]]
        blocked_ids = [item["id"] for item in result["blocked"]]

        assert schema_id in ready_ids
        assert sample_todos["docs"].id in ready_ids
        assert auth_id in blocked_ids
        assert ui_id in blocked_ids
        assert result["summary"]["ready_count"] == 2
        assert result["summary"]["blocked_count"] == 2

    def test_get_ready_items_completed_blockers(self, sample_todos):
        """Test that items become ready when their blockers are completed."""
        schema_id = sample_todos["schema"].id
        auth_id = sample_todos["auth"].id

        # Create dependency
        todo_mcp.add_dependency(blocker_id=schema_id, blocked_id=auth_id)

        # Mark schema as done
        todo_mcp.update_item(item_id=schema_id, status="done")

        result = todo_mcp.get_ready_items()

        # Now auth should be ready since its blocker is done
        ready_ids = [item["id"] for item in result["ready"]]
        assert auth_id in ready_ids


class TestDependencyChain:
    """Test dependency chain analysis."""

    def test_get_dependency_chain_upstream(self, sample_todos):
        """Test getting upstream dependencies."""
        schema_id = sample_todos["schema"].id
        auth_id = sample_todos["auth"].id
        ui_id = sample_todos["ui"].id

        # Create chain: schema -> auth -> ui
        todo_mcp.add_dependency(blocker_id=schema_id, blocked_id=auth_id)
        todo_mcp.add_dependency(blocker_id=auth_id, blocked_id=ui_id)

        result = todo_mcp.get_dependency_chain(item_id=ui_id, direction="upstream")

        assert "error" not in result
        assert result["item"]["id"] == ui_id
        assert "upstream" in result
        assert len(result["upstream"]) == 1

        # Check the chain: ui <- auth <- schema
        auth_blocker = result["upstream"][0]
        assert auth_blocker["id"] == auth_id
        assert len(auth_blocker["blockers"]) == 1
        assert auth_blocker["blockers"][0]["id"] == schema_id

    def test_get_dependency_chain_downstream(self, sample_todos):
        """Test getting downstream dependencies."""
        schema_id = sample_todos["schema"].id
        auth_id = sample_todos["auth"].id
        ui_id = sample_todos["ui"].id
        docs_id = sample_todos["docs"].id

        # Create dependencies: auth blocks both ui and docs
        todo_mcp.add_dependency(blocker_id=schema_id, blocked_id=auth_id)
        todo_mcp.add_dependency(blocker_id=auth_id, blocked_id=ui_id)
        todo_mcp.add_dependency(blocker_id=auth_id, blocked_id=docs_id)

        result = todo_mcp.get_dependency_chain(item_id=auth_id, direction="downstream")

        assert "error" not in result
        assert result["item"]["id"] == auth_id
        assert "downstream" in result
        assert len(result["downstream"]) == 2

        blocked_ids = [item["id"] for item in result["downstream"]]
        assert ui_id in blocked_ids
        assert docs_id in blocked_ids

    def test_get_dependency_chain_both(self, sample_todos):
        """Test getting full dependency chain."""
        schema_id = sample_todos["schema"].id
        auth_id = sample_todos["auth"].id
        ui_id = sample_todos["ui"].id

        # Create chain: schema -> auth -> ui
        todo_mcp.add_dependency(blocker_id=schema_id, blocked_id=auth_id)
        todo_mcp.add_dependency(blocker_id=auth_id, blocked_id=ui_id)

        result = todo_mcp.get_dependency_chain(item_id=auth_id, direction="both")

        assert "error" not in result
        assert result["item"]["id"] == auth_id
        assert "upstream" in result
        assert "downstream" in result
        assert len(result["upstream"]) == 1
        assert len(result["downstream"]) == 1
        assert result["upstream"][0]["id"] == schema_id
        assert result["downstream"][0]["id"] == ui_id

    def test_get_dependency_chain_invalid_direction(self, sample_todos):
        """Test error with invalid direction."""
        result = todo_mcp.get_dependency_chain(item_id=1, direction="invalid")

        assert "error" in result
        assert "Direction must be" in result["error"]

    def test_get_dependency_chain_nonexistent_item(self, sample_todos):
        """Test error with non-existent item."""
        result = todo_mcp.get_dependency_chain(item_id=999)

        assert "error" in result
        assert "not found" in result["error"]


class TestDependencyMigration:
    """Test that migrations work correctly."""

    def test_migration_creates_dependency_table(self):
        """Test that the migration creates the dependency table."""
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_db_path = pathlib.Path(temp_dir) / "test_migration.db"
            temp_engine = create_engine(f"sqlite:///{temp_db_path}")

            with patch.object(todo_mcp, "engine", temp_engine):
                # Create base tables and run migrations
                todo_mcp.create_db_and_tables()

                # Verify dependency table exists
                with Session(temp_engine) as session:
                    # This should not raise an exception if table exists
                    result = session.exec(
                        todo_mcp.text("SELECT name FROM sqlite_master WHERE type='table' AND name='tododependency'")
                    )
                    table_exists = result.first() is not None
                    assert table_exists


if __name__ == "__main__":
    pytest.main([__file__])
