import pytest
from sqlmodel import SQLModel, create_engine
from todo_mcp import add_item, list_items, update_item, mark_item_done, remove_item, assistant_workflow_guide
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


def test_pr_workflow_basic_lifecycle(temp_db):
    """Test basic PR lifecycle: add -> start work -> complete"""

    # Add a PR item
    result = add_item(
        description="Implement user authentication system", priority="high", tags="backend,security,feature"
    )

    assert "error" not in result
    assert result["description"] == "Implement user authentication system"
    assert result["priority"] == "high"
    assert result["status"] == "open"
    assert result["tags"] == "backend,security,feature"
    item_id = result["id"]

    # Start working on it
    update_result = update_item(item_id, status="in_progress")
    assert update_result["status"] == "in_progress"

    # Complete the work
    done_result = mark_item_done(item_id)
    assert done_result["status"] == "done"


def test_pr_tagging_and_filtering(temp_db):
    """Test tagging system for PR categorization"""

    # Add multiple PRs with different tags
    add_item(description="Add API rate limiting", priority="high", tags="backend,security,enhancement")
    add_item(description="Fix responsive design on mobile", priority="medium", tags="frontend,bugfix,ui")
    add_item(description="Update API documentation", priority="low", tags="docs,api,enhancement")

    # Test tag filtering
    backend_items = list_items(tag_filter="backend")
    assert len(backend_items["items"]) == 1
    assert backend_items["items"][0]["description"] == "Add API rate limiting"

    # Test priority filtering
    high_items = list_items(priority_filter="high")
    assert len(high_items["items"]) == 1
    assert high_items["items"][0]["priority"] == "high"

    # Test multiple tag filtering (should find enhancement items)
    enhancement_items = list_items(tag_filter="enhancement")
    assert len(enhancement_items["items"]) == 2


def test_pr_grooming_activities(temp_db):
    """Test grooming activities: updating descriptions, tags, priorities"""

    # Add a PR
    result = add_item(description="Initial task description", priority="medium", tags="backend,todo")
    item_id = result["id"]

    # Grooming: Update description and tags after discussion
    groomed = update_item(
        item_id,
        description="Implement OAuth2 authentication with JWT tokens",
        priority="high",
        tags="backend,security,oauth,feature",
    )

    assert groomed["description"] == "Implement OAuth2 authentication with JWT tokens"
    assert groomed["priority"] == "high"
    assert groomed["tags"] == "backend,security,oauth,feature"

    # Grooming: Remove unnecessary tag
    refined = update_item(item_id, tags="backend,security,oauth")
    assert refined["tags"] == "backend,security,oauth"


def test_pr_status_reporting(temp_db):
    """Test generating status reports for project management"""

    # Add items in different states
    item1 = add_item("Complete feature A", priority="high", tags="feature")
    item2 = add_item("Fix bug B", priority="medium", tags="bugfix")
    add_item("Add tests C", priority="low", tags="testing")

    # Move items to different states
    update_item(item1["id"], status="in_progress")
    mark_item_done(item2["id"])
    # third item remains open

    # Generate reports by status
    open_items = list_items(status_filter="open")
    assert len(open_items["items"]) == 1
    assert open_items["items"][0]["description"] == "Add tests C"

    in_progress_items = list_items(status_filter="in_progress")
    assert len(in_progress_items["items"]) == 1
    assert in_progress_items["items"][0]["description"] == "Complete feature A"

    done_items = list_items(status_filter="done")
    assert len(done_items["items"]) == 1
    assert done_items["items"][0]["description"] == "Fix bug B"

    # All items report
    all_items = list_items(show_all_statuses=True)
    assert len(all_items["items"]) == 3


def test_pr_priority_management(temp_db):
    """Test priority-based filtering and sorting for PR management"""

    # Add items with different priorities
    add_item("Critical security fix", priority="high", tags="security,bugfix")
    add_item("Nice to have feature", priority="low", tags="feature")
    add_item("Important enhancement", priority="medium", tags="enhancement")

    # Filter by high priority items
    high_priority = list_items(priority_filter="high")
    assert len(high_priority["items"]) == 1
    assert high_priority["items"][0]["description"] == "Critical security fix"

    # Sort by priority (high first)
    sorted_items = list_items(sort_by="priority")
    priorities = [item["priority"] for item in sorted_items["items"]]
    assert priorities == ["high", "medium", "low"]


def test_pr_cleanup_workflow(temp_db):
    """Test removing obsolete or cancelled PRs"""

    # Add some items
    item1 = add_item("Feature that's no longer needed", priority="low")
    add_item("Important feature", priority="high")

    # Mark first as cancelled (alternative to deletion)
    cancelled = update_item(item1["id"], status="cancelled")
    assert cancelled["status"] == "cancelled"

    # Or remove completely
    removal_result = remove_item(item1["id"])
    assert "error" not in removal_result

    # Verify only important item remains
    remaining = list_items(show_all_statuses=True)
    assert len(remaining["items"]) == 1
    assert remaining["items"][0]["description"] == "Important feature"


def test_pr_due_date_management(temp_db):
    """Test due dates for release planning"""

    # Add PR with due date
    result = add_item(
        description="Feature for Q1 release", priority="high", due_date_str="2024-03-31", tags="feature,q1-release"
    )

    assert result["due_date"] == "2024-03-31"

    # Sort by due date
    items = list_items(sort_by="due_date")
    assert len(items["items"]) == 1

    # Update due date during grooming
    updated = update_item(result["id"], due_date_str="2024-04-15")
    assert updated["due_date"] == "2024-04-15"


def test_pr_complex_filtering(temp_db):
    """Test complex filtering scenarios for project management"""

    # Add various PRs
    add_item("Backend API work", priority="high", tags="backend,api", due_date_str="2024-02-01")
    add_item("Frontend UI fix", priority="medium", tags="frontend,ui,bugfix")
    add_item("Backend security enhancement", priority="high", tags="backend,security")
    add_item("API documentation", priority="low", tags="docs,api")

    # Filter: High priority backend items
    backend_high = list_items(priority_filter="high", tag_filter="backend")
    assert len(backend_high["items"]) == 2

    # Filter items with specific tags
    api_items = list_items(tag_filter="api")
    assert len(api_items["items"]) == 2

    # Combined filtering
    all_items = list_items(show_all_statuses=True, sort_by="priority")
    assert len(all_items["items"]) == 4


def test_assistant_workflow_guide():
    """Test the assistant workflow guide tool"""

    guide_result = assistant_workflow_guide()

    assert "guide" in guide_result
    guide_content = guide_result["guide"]

    # Check that guide contains key sections
    assert "Code Assistant Project Management Workflow Guide" in guide_content
    assert "Quick Start Workflow" in guide_content
    assert "Adding New PR Tasks" in guide_content
    assert "Work Lifecycle" in guide_content
    assert "Reporting & Status Tracking" in guide_content
    assert "Recommended Tagging Strategy" in guide_content
    assert "Example Daily Workflow" in guide_content

    # Check for important workflow steps
    assert 'update_item(item_id=123, status="in_progress")' in guide_content
    assert "mark_item_done" in guide_content
    assert "Run tests" in guide_content
    assert "ONLY mark done if tests pass" in guide_content

    # Check for tagging examples
    assert "backend,security,oauth,feature" in guide_content
    assert "feature" in guide_content and "bugfix" in guide_content

    # Verify it's a substantial guide (not just a stub)
    assert len(guide_content) > 2000  # Should be a comprehensive guide
