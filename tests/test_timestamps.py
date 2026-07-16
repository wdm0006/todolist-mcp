from datetime import datetime, timezone

import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session, SQLModel, create_engine

import kanban_web
import todo_mcp


@pytest.fixture
def test_engine(tmp_path, monkeypatch):
    engine = create_engine(f"sqlite:///{tmp_path / 'timestamps.db'}")
    SQLModel.metadata.create_all(engine)
    monkeypatch.setattr(todo_mcp, "engine", engine)
    monkeypatch.setattr(kanban_web, "engine", engine)
    yield engine


def utc_bounds():
    return datetime.now(timezone.utc).replace(tzinfo=None)


def assert_naive_utc_timestamp(value, before, after):
    timestamp = datetime.fromisoformat(value) if isinstance(value, str) else value
    assert before <= timestamp <= after
    assert timestamp.tzinfo is None
    if isinstance(value, str):
        assert not value.endswith(("Z", "+00:00"))


def test_mcp_operations_emit_naive_utc_timestamps(test_engine):
    before_create = utc_bounds()
    blocker = todo_mcp.add_item("Blocker")
    blocked = todo_mcp.add_item("Blocked")
    after_create = utc_bounds()

    for item in (blocker, blocked):
        assert_naive_utc_timestamp(item["created_at"], before_create, after_create)
        assert_naive_utc_timestamp(item["updated_at"], before_create, after_create)

    before_dependency = utc_bounds()
    dependency = todo_mcp.add_dependency(blocker["id"], blocked["id"])["dependency"]
    after_dependency = utc_bounds()
    assert_naive_utc_timestamp(dependency["created_at"], before_dependency, after_dependency)

    before_update = utc_bounds()
    updated = todo_mcp.update_item(blocked["id"], status="in_progress")
    after_update = utc_bounds()
    assert_naive_utc_timestamp(updated["updated_at"], before_update, after_update)


def test_web_status_update_uses_naive_utc_timestamp(test_engine):
    with Session(test_engine) as session:
        todo = todo_mcp.Todo(description="Move me")
        session.add(todo)
        session.commit()
        session.refresh(todo)
        todo_id = todo.id

    def override_get_session():
        with Session(test_engine) as session:
            yield session

    kanban_web.app.dependency_overrides[kanban_web.get_session] = override_get_session
    try:
        before = utc_bounds()
        response = TestClient(kanban_web.app).put(f"/todos/{todo_id}/status", data={"status": "done"})
        after = utc_bounds()
    finally:
        kanban_web.app.dependency_overrides.clear()

    assert response.status_code == 200
    with Session(test_engine) as session:
        updated_at = session.get(todo_mcp.Todo, todo_id).updated_at
    assert_naive_utc_timestamp(updated_at, before, after)
