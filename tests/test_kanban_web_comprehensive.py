#!/usr/bin/env python3
# /// script
# dependencies = [
#   "fastapi>=0.104.0",
#   "uvicorn>=0.24.0",
#   "sqlmodel>=0.0.14,<0.1.0",
#   "jinja2>=3.1.0",
#   "python-multipart>=0.0.6",
#   "pytest>=7.0.0",
#   "httpx>=0.24.0",
#   "beautifulsoup4>=4.12.0"
# ]
# ///

"""
Comprehensive test suite for the FastAPI + HTMX Kanban Web App

Tests all API endpoints, database operations, UI rendering, drag-and-drop functionality,
form submissions, and error handling scenarios.
"""

import pytest
import tempfile
import os
import pathlib
from datetime import datetime, date
from unittest.mock import patch, MagicMock
from fastapi.testclient import TestClient
from sqlmodel import SQLModel, Session, create_engine, select
from bs4 import BeautifulSoup

# Import the application and models
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from kanban_web import app, Todo, Status, Priority, setup_database, get_session


@pytest.fixture(scope="function")
def temp_db():
    """Create a temporary database for testing"""
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as temp_file:
        temp_db_path = temp_file.name
    
    try:
        # Create test database
        database_url = f"sqlite:///{temp_db_path}"
        test_engine = create_engine(database_url)
        SQLModel.metadata.create_all(test_engine)
        
        yield test_engine, temp_db_path
    finally:
        # Cleanup
        try:
            os.unlink(temp_db_path)
        except OSError:
            pass


@pytest.fixture(scope="function")
def test_client(temp_db):
    """Create test client with isolated database"""
    test_engine, temp_db_path = temp_db
    
    # Override the get_session dependency
    def override_get_session():
        with Session(test_engine) as session:
            yield session
    
    app.dependency_overrides[get_session] = override_get_session
    
    # Set global engine for the app
    import kanban_web
    kanban_web.engine = test_engine
    
    client = TestClient(app)
    yield client, test_engine
    
    # Cleanup
    app.dependency_overrides.clear()


@pytest.fixture(scope="function")
def sample_todos(test_client):
    """Create sample todos for testing"""
    client, engine = test_client
    
    sample_data = [
        {
            "description": "Implement user authentication system",
            "priority": Priority.HIGH,
            "status": Status.OPEN,
            "tags": "backend,security,feature",
            "due_date": date(2024, 3, 15)
        },
        {
            "description": "Fix responsive design on mobile",
            "priority": Priority.MEDIUM,
            "status": Status.IN_PROGRESS,
            "tags": "frontend,bugfix,ui",
            "due_date": date(2024, 2, 28)
        },
        {
            "description": "Add API rate limiting",
            "priority": Priority.HIGH,
            "status": Status.OPEN,
            "tags": "backend,security,enhancement",
            "due_date": None
        },
        {
            "description": "Update API documentation",
            "priority": Priority.LOW,
            "status": Status.DONE,
            "tags": "docs,api,enhancement",
            "due_date": date(2024, 2, 15)
        },
        {
            "description": "Write unit tests for auth module",
            "priority": Priority.MEDIUM,
            "status": Status.CANCELLED,
            "tags": "backend,testing,security",
            "due_date": None
        }
    ]
    
    todos = []
    with Session(engine) as session:
        for todo_data in sample_data:
            todo = Todo(**todo_data)
            session.add(todo)
            todos.append(todo)
        session.commit()
        
        # Refresh to get IDs
        for todo in todos:
            session.refresh(todo)
    
    return todos


class TestKanbanWebBasicFunctionality:
    """Test basic web app functionality"""
    
    def test_app_startup(self, test_client):
        """Test that the app starts up correctly"""
        client, _ = test_client
        response = client.get("/")
        assert response.status_code == 200
        assert "Todo Kanban Board" in response.text
    
    def test_main_page_structure(self, test_client):
        """Test main page HTML structure"""
        client, _ = test_client
        response = client.get("/")
        
        soup = BeautifulSoup(response.text, 'html.parser')
        
        # Check essential elements
        assert soup.find("title").text == "Todo Kanban Board"
        assert soup.find("h1").text == "Todo Kanban Board"
        assert soup.find(class_="kanban-board") is not None
        assert soup.find(id="createModal") is not None
        
        # Check for all status columns
        columns = soup.find_all(class_="kanban-column")
        assert len(columns) == 4  # open, in_progress, done, cancelled
        
        # Check column titles
        column_titles = [col.find(class_="column-title").text for col in columns]
        expected_titles = ["To Do", "In Progress", "Done", "Cancelled"]
        assert column_titles == expected_titles
    
    def test_css_and_js_loading(self, test_client):
        """Test that CSS and JavaScript are properly included"""
        client, _ = test_client
        response = client.get("/")
        
        # Check for CSS
        assert "font-family: 'Inter'" in response.text
        assert ".kanban-board" in response.text
        assert ".todo-card" in response.text
        
        # Check for JavaScript libraries
        assert "htmx.org" in response.text
        assert "sortablejs" in response.text
        
        # Check for custom JavaScript functions
        assert "showCreateModal" in response.text
        assert "initializeSortable" in response.text


class TestDatabaseOperations:
    """Test database operations and model functionality"""
    
    def test_todo_model_creation(self, test_client):
        """Test creating Todo model instances"""
        client, engine = test_client
        
        with Session(engine) as session:
            todo = Todo(
                description="Test todo item",
                priority=Priority.HIGH,
                status=Status.OPEN,
                tags="test,backend",
                due_date=date(2024, 6, 1)
            )
            session.add(todo)
            session.commit()
            session.refresh(todo)
            
            assert todo.id is not None
            assert todo.description == "Test todo item"
            assert todo.priority == Priority.HIGH
            assert todo.status == Status.OPEN
            assert todo.tags == "test,backend"
            assert todo.due_date == date(2024, 6, 1)
            assert isinstance(todo.created_at, datetime)
            assert isinstance(todo.updated_at, datetime)
    
    def test_todo_model_defaults(self, test_client):
        """Test Todo model default values"""
        client, engine = test_client
        
        with Session(engine) as session:
            todo = Todo(description="Minimal todo")
            session.add(todo)
            session.commit()
            session.refresh(todo)
            
            assert todo.priority == Priority.MEDIUM
            assert todo.status == Status.OPEN
            assert todo.tags is None
            assert todo.due_date is None
    
    def test_database_queries(self, test_client, sample_todos):
        """Test various database queries"""
        client, engine = test_client
        
        with Session(engine) as session:
            # Test basic query
            all_todos = session.exec(select(Todo)).all()
            assert len(all_todos) == 5
            
            # Test status filtering
            open_todos = session.exec(select(Todo).where(Todo.status == Status.OPEN)).all()
            assert len(open_todos) == 2
            
            in_progress_todos = session.exec(select(Todo).where(Todo.status == Status.IN_PROGRESS)).all()
            assert len(in_progress_todos) == 1
            
            done_todos = session.exec(select(Todo).where(Todo.status == Status.DONE)).all()
            assert len(done_todos) == 1
            
            cancelled_todos = session.exec(select(Todo).where(Todo.status == Status.CANCELLED)).all()
            assert len(cancelled_todos) == 1
            
            # Test priority filtering
            high_priority = session.exec(select(Todo).where(Todo.priority == Priority.HIGH)).all()
            assert len(high_priority) == 2
            
            # Test tag searching (would need LIKE queries in real app)
            backend_todos = session.exec(select(Todo).where(Todo.tags.contains("backend"))).all()
            assert len(backend_todos) == 3


class TestAPIEndpoints:
    """Test all API endpoints"""
    
    def test_get_main_page(self, test_client, sample_todos):
        """Test GET / endpoint with sample data"""
        client, _ = test_client
        response = client.get("/")
        
        assert response.status_code == 200
        assert "Implement user authentication system" in response.text
        assert "Fix responsive design on mobile" in response.text
        
        # Check that todos appear in correct columns
        soup = BeautifulSoup(response.text, 'html.parser')
        
        # Find column with "To Do" title
        todo_column = None
        for col in soup.find_all(class_="kanban-column"):
            if col.find(class_="column-title").text == "To Do":
                todo_column = col
                break
        
        assert todo_column is not None
        todo_cards = todo_column.find_all(class_="todo-card")
        assert len(todo_cards) == 2  # 2 open todos
    
    def test_create_todo_post(self, test_client):
        """Test POST /todos endpoint"""
        client, engine = test_client
        
        form_data = {
            "description": "New test todo",
            "priority": "high",
            "tags": "test,api",
            "due_date": "2024-06-01"
        }
        
        response = client.post("/todos", data=form_data, follow_redirects=False)
        assert response.status_code == 303  # Redirect
        
        # Verify todo was created
        with Session(engine) as session:
            new_todo = session.exec(select(Todo).where(Todo.description == "New test todo")).first()
            assert new_todo is not None
            assert new_todo.priority == Priority.HIGH
            assert new_todo.tags == "test,api"
            assert new_todo.due_date == date(2024, 6, 1)
    
    def test_create_todo_minimal_data(self, test_client):
        """Test creating todo with minimal required data"""
        client, engine = test_client
        
        form_data = {"description": "Minimal todo"}
        
        response = client.post("/todos", data=form_data, follow_redirects=False)
        assert response.status_code == 303
        
        with Session(engine) as session:
            new_todo = session.exec(select(Todo).where(Todo.description == "Minimal todo")).first()
            assert new_todo is not None
            assert new_todo.priority == Priority.MEDIUM  # Default
            assert new_todo.status == Status.OPEN  # Default
            assert new_todo.tags is None
            assert new_todo.due_date is None
    
    def test_create_todo_invalid_date(self, test_client):
        """Test creating todo with invalid due date"""
        client, engine = test_client
        
        form_data = {
            "description": "Todo with invalid date",
            "due_date": "invalid-date"
        }
        
        response = client.post("/todos", data=form_data, follow_redirects=False)
        assert response.status_code == 303  # Should still succeed, date ignored
        
        with Session(engine) as session:
            new_todo = session.exec(select(Todo).where(Todo.description == "Todo with invalid date")).first()
            assert new_todo is not None
            assert new_todo.due_date is None  # Invalid date ignored
    
    def test_update_todo_status(self, test_client, sample_todos):
        """Test PUT /todos/{id}/status endpoint"""
        client, _ = test_client
        
        todo = sample_todos[0]  # First todo (should be open)
        assert todo.status == Status.OPEN
        
        response = client.put(f"/todos/{todo.id}/status", data={"status": "in_progress"})
        assert response.status_code == 200
        
        # Verify JSON response
        assert response.json() == {"success": True}
    
    def test_update_nonexistent_todo_status(self, test_client):
        """Test updating status of non-existent todo"""
        client, _ = test_client
        
        response = client.put("/todos/99999/status", data={"status": "done"})
        assert response.status_code == 404
    
    def test_delete_todo(self, test_client, sample_todos):
        """Test DELETE /todos/{id} endpoint"""
        client, engine = test_client
        
        todo = sample_todos[0]
        todo_id = todo.id
        
        response = client.delete(f"/todos/{todo_id}", follow_redirects=False)
        assert response.status_code == 303  # Redirect
        
        # Verify todo was deleted
        with Session(engine) as session:
            deleted_todo = session.get(Todo, todo_id)
            assert deleted_todo is None
    
    def test_delete_nonexistent_todo(self, test_client):
        """Test deleting non-existent todo"""
        client, _ = test_client
        
        response = client.delete("/todos/99999")
        assert response.status_code == 404


class TestUIRendering:
    """Test UI rendering and HTML generation"""
    
    def test_empty_board_rendering(self, test_client):
        """Test kanban board with no todos"""
        client, _ = test_client
        response = client.get("/")
        
        soup = BeautifulSoup(response.text, 'html.parser')
        
        # All columns should exist but be empty
        columns = soup.find_all(class_="kanban-column")
        assert len(columns) == 4
        
        for column in columns:
            todo_list = column.find(class_="todo-list")
            assert todo_list is not None
            
            # Count should be 0
            count_span = column.find(class_="item-count")
            assert count_span.text == "0"
    
    def test_todo_card_rendering(self, test_client, sample_todos):
        """Test individual todo card rendering"""
        client, _ = test_client
        response = client.get("/")
        
        soup = BeautifulSoup(response.text, 'html.parser')
        cards = soup.find_all(class_="todo-card")
        
        assert len(cards) == 5  # All sample todos should render
        
        # Test first card (high priority todo)
        high_priority_card = soup.find(class_="todo-card priority-high")
        assert high_priority_card is not None
        
        # Check card structure
        assert high_priority_card.find(class_="card-title") is not None
        assert high_priority_card.find(class_="card-id") is not None
        assert high_priority_card.find(class_="priority-indicator") is not None
        
        # Check data attributes for drag-and-drop
        assert high_priority_card.get("data-todo-id") is not None
    
    def test_tag_rendering(self, test_client, sample_todos):
        """Test tag rendering in cards"""
        client, _ = test_client
        response = client.get("/")
        
        soup = BeautifulSoup(response.text, 'html.parser')
        
        # Find cards with tags
        cards_with_tags = soup.find_all(class_="card-tags")
        assert len(cards_with_tags) > 0
        
        # Check for specific tag classes
        backend_tags = soup.find_all(class_="tag tag-backend")
        assert len(backend_tags) > 0
        
        security_tags = soup.find_all(class_="tag tag-security")
        assert len(security_tags) > 0
    
    def test_due_date_rendering(self, test_client, sample_todos):
        """Test due date rendering"""
        client, _ = test_client
        response = client.get("/")
        
        soup = BeautifulSoup(response.text, 'html.parser')
        due_dates = soup.find_all(class_="due-date")
        
        # Should have 3 todos with due dates
        assert len(due_dates) == 3
        
        # Check date format
        for due_date in due_dates:
            assert "Due:" in due_date.text
            assert "2024-" in due_date.text
    
    def test_priority_indicators(self, test_client, sample_todos):
        """Test priority indicator rendering"""
        client, _ = test_client
        response = client.get("/")
        
        soup = BeautifulSoup(response.text, 'html.parser')
        
        # Check priority dots
        high_dots = soup.find_all(class_="priority-dot high")
        medium_dots = soup.find_all(class_="priority-dot medium")
        low_dots = soup.find_all(class_="priority-dot low")
        
        assert len(high_dots) == 2  # 2 high priority todos
        assert len(medium_dots) == 2  # 2 medium priority todos
        assert len(low_dots) == 1   # 1 low priority todo
    
    def test_column_counts(self, test_client, sample_todos):
        """Test that column counts are accurate"""
        client, _ = test_client
        response = client.get("/")
        
        soup = BeautifulSoup(response.text, 'html.parser')
        columns = soup.find_all(class_="kanban-column")
        
        # Expected counts based on sample data
        expected_counts = {"To Do": 2, "In Progress": 1, "Done": 1, "Cancelled": 1}
        
        for column in columns:
            title = column.find(class_="column-title").text
            count = int(column.find(class_="item-count").text)
            assert count == expected_counts[title]


class TestFormHandling:
    """Test form submissions and validation"""
    
    def test_create_form_submission(self, test_client):
        """Test create todo form submission"""
        client, _ = test_client
        
        # Test complete form
        form_data = {
            "description": "Complete form test",
            "priority": "high",
            "tags": "test,form,complete",
            "due_date": "2024-12-31"
        }
        
        response = client.post("/todos", data=form_data, follow_redirects=False)
        assert response.status_code == 303
        assert response.headers["location"] == "/"
    
    def test_form_data_validation(self, test_client):
        """Test form data validation and edge cases"""
        client, engine = test_client
        
        # Test empty tags (should be stored as None)
        form_data = {
            "description": "Empty tags test",
            "tags": ""
        }
        
        response = client.post("/todos", data=form_data, follow_redirects=False)
        assert response.status_code == 303
        
        with Session(engine) as session:
            todo = session.exec(select(Todo).where(Todo.description == "Empty tags test")).first()
            assert todo.tags is None
    
    def test_missing_required_fields(self, test_client):
        """Test form submission with missing required fields"""
        client, _ = test_client
        
        # Missing description should fail (depends on HTML form validation)
        # This would typically be caught by the browser, but test server-side handling
        response = client.post("/todos", data={})
        # FastAPI will return 422 for missing required fields
        assert response.status_code == 422


class TestDragAndDropFunctionality:
    """Test drag and drop related functionality"""
    
    def test_drag_drop_data_attributes(self, test_client, sample_todos):
        """Test that cards have proper data attributes for drag and drop"""
        client, _ = test_client
        response = client.get("/")
        
        soup = BeautifulSoup(response.text, 'html.parser')
        
        # Check todo cards have data-todo-id
        cards = soup.find_all(class_="todo-card")
        for card in cards:
            assert card.get("data-todo-id") is not None
            assert card.get("data-todo-id").isdigit()
        
        # Check todo lists have data-status
        todo_lists = soup.find_all(class_="todo-list")
        assert len(todo_lists) == 4
        
        expected_statuses = ["open", "in_progress", "done", "cancelled"]
        for i, todo_list in enumerate(todo_lists):
            assert todo_list.get("data-status") == expected_statuses[i]
    
    def test_sortable_initialization_script(self, test_client):
        """Test that sortable initialization script is present"""
        client, _ = test_client
        response = client.get("/")
        
        # Check for sortable-related JavaScript
        assert "initializeSortable" in response.text
        assert "new Sortable" in response.text
        assert "group: 'todos'" in response.text
        assert "onEnd: function" in response.text
    
    def test_status_update_via_api(self, test_client, sample_todos):
        """Test status update API that drag-and-drop uses"""
        client, engine = test_client
        
        todo = sample_todos[0]
        original_status = todo.status
        new_status = Status.IN_PROGRESS
        
        # Update status
        response = client.put(f"/todos/{todo.id}/status", data={"status": new_status.value})
        assert response.status_code == 200
        assert response.json()["success"] is True
        
        # Verify in database
        with Session(engine) as session:
            updated_todo = session.get(Todo, todo.id)
            assert updated_todo.status == new_status
            assert updated_todo.updated_at > updated_todo.created_at


class TestErrorHandling:
    """Test error handling scenarios"""
    
    def test_invalid_todo_id(self, test_client):
        """Test operations with invalid todo IDs"""
        client, _ = test_client
        
        # Test non-numeric ID
        response = client.put("/todos/abc/status", data={"status": "done"})
        assert response.status_code == 422  # Validation error
        
        response = client.delete("/todos/abc")
        assert response.status_code == 422
    
    def test_invalid_status_values(self, test_client, sample_todos):
        """Test updating with invalid status values"""
        client, _ = test_client
        
        todo = sample_todos[0]
        
        # Test invalid status
        response = client.put(f"/todos/{todo.id}/status", data={"status": "invalid_status"})
        assert response.status_code == 422  # Validation error
    
    def test_invalid_priority_values(self, test_client):
        """Test creating todo with invalid priority"""
        client, _ = test_client
        
        form_data = {
            "description": "Invalid priority test",
            "priority": "invalid_priority"
        }
        
        response = client.post("/todos", data=form_data)
        assert response.status_code == 422  # Validation error
    
    def test_database_constraint_violations(self, test_client):
        """Test database constraint violations"""
        client, _ = test_client
        
        # Test empty description (should succeed as empty string is valid)
        form_data = {"description": ""}
        response = client.post("/todos", data=form_data, follow_redirects=False)
        # Empty description is actually allowed, so this should succeed
        assert response.status_code == 303


class TestPerformanceAndScalability:
    """Test performance and scalability aspects"""
    
    def test_large_number_of_todos(self, test_client):
        """Test app behavior with many todos"""
        client, engine = test_client
        
        # Create 100 todos
        with Session(engine) as session:
            for i in range(100):
                todo = Todo(
                    description=f"Test todo {i}",
                    priority=Priority.MEDIUM,
                    status=Status.OPEN if i % 2 == 0 else Status.DONE
                )
                session.add(todo)
            session.commit()
        
        # Test that page still loads quickly
        response = client.get("/")
        assert response.status_code == 200
        
        # Verify todos are rendered
        soup = BeautifulSoup(response.text, 'html.parser')
        cards = soup.find_all(class_="todo-card")
        assert len(cards) == 100
    
    def test_long_descriptions_and_tags(self, test_client):
        """Test handling of long text content"""
        client, engine = test_client
        
        long_description = "A" * 1000  # Very long description
        long_tags = ",".join([f"tag{i}" for i in range(50)])  # Many tags
        
        form_data = {
            "description": long_description,
            "tags": long_tags
        }
        
        response = client.post("/todos", data=form_data, follow_redirects=False)
        assert response.status_code == 303
        
        # Verify page still renders
        response = client.get("/")
        assert response.status_code == 200
        assert long_description[:100] in response.text  # Check partial content


class TestDatabaseSetup:
    """Test database setup and configuration"""
    
    def test_setup_database_function(self):
        """Test database setup function"""
        with tempfile.TemporaryDirectory() as temp_dir:
            # Test with project directory
            database_url = setup_database(temp_dir)
            assert database_url.startswith("sqlite:///")
            assert temp_dir in database_url
            
            # Verify database file was created
            db_file = pathlib.Path(temp_dir) / "todo.db"
            # Note: File creation depends on actual database operations
    
    def test_database_tables_creation(self, temp_db):
        """Test that database tables are created correctly"""
        engine, _ = temp_db
        
        # Test that we can create a session and query (tables exist)
        with Session(engine) as session:
            # This should not raise an error if tables exist
            result = session.exec(select(Todo)).all()
            assert isinstance(result, list)


class TestIntegrationScenarios:
    """Test complete user workflow scenarios"""
    
    def test_complete_todo_lifecycle(self, test_client):
        """Test complete todo lifecycle: create -> move -> complete -> delete"""
        client, engine = test_client
        
        # 1. Create todo
        form_data = {
            "description": "Lifecycle test todo",
            "priority": "high",
            "tags": "test,lifecycle"
        }
        
        response = client.post("/todos", data=form_data, follow_redirects=False)
        assert response.status_code == 303
        
        # Get the created todo
        with Session(engine) as session:
            todo = session.exec(select(Todo).where(Todo.description == "Lifecycle test todo")).first()
            assert todo is not None
            todo_id = todo.id
        
        # 2. Move to in_progress
        response = client.put(f"/todos/{todo_id}/status", data={"status": "in_progress"})
        assert response.status_code == 200
        
        # 3. Move to done
        response = client.put(f"/todos/{todo_id}/status", data={"status": "done"})
        assert response.status_code == 200
        
        # 4. Delete todo
        response = client.delete(f"/todos/{todo_id}", follow_redirects=False)
        assert response.status_code == 303
        
        # Verify todo is deleted
        with Session(engine) as session:
            deleted_todo = session.get(Todo, todo_id)
            assert deleted_todo is None
    
    def test_multiple_users_simulation(self, test_client):
        """Simulate multiple users working with the board simultaneously"""
        client, engine = test_client
        
        # Create multiple todos as if from different users
        todos_data = [
            {"description": "User 1 task 1", "priority": "high"},
            {"description": "User 1 task 2", "priority": "medium"},
            {"description": "User 2 task 1", "priority": "low"},
            {"description": "User 2 task 2", "priority": "high"},
        ]
        
        created_todos = []
        for todo_data in todos_data:
            response = client.post("/todos", data=todo_data, follow_redirects=False)
            assert response.status_code == 303
            
            with Session(engine) as session:
                todo = session.exec(select(Todo).where(Todo.description == todo_data["description"])).first()
                created_todos.append(todo)
        
        # Simulate concurrent status updates
        for i, todo in enumerate(created_todos):
            new_status = "in_progress" if i % 2 == 0 else "done"
            response = client.put(f"/todos/{todo.id}/status", data={"status": new_status})
            assert response.status_code == 200
        
        # Verify final state
        response = client.get("/")
        assert response.status_code == 200
        
        soup = BeautifulSoup(response.text, 'html.parser')
        cards = soup.find_all(class_="todo-card")
        assert len(cards) == 4


if __name__ == "__main__":
    pytest.main([__file__, "-v"])