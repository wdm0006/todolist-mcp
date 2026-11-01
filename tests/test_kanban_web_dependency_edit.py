"""POST/DELETE /todos/{id}/dependencies and the modal's blocker picker and remove controls."""

import os
import sys

import pytest
from bs4 import BeautifulSoup
from fastapi.testclient import TestClient
from sqlmodel import Session, SQLModel, create_engine, select

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import shutil  # noqa: E402

import kanban_web  # noqa: E402
from kanban_web import Status, TodoDependency  # noqa: E402
from test_kanban_web_dependencies import HOSTILE, _render, add_edges, add_todos  # noqa: E402


@pytest.fixture
def env(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path / 'todo.db'}")
    SQLModel.metadata.create_all(engine)

    def override_get_session():
        with Session(engine) as session:
            yield session

    kanban_web.app.dependency_overrides[kanban_web.get_session] = override_get_session
    yield TestClient(kanban_web.app), engine
    kanban_web.app.dependency_overrides.clear()


def edges(engine):
    with Session(engine) as session:
        return sorted((d.blocker_id, d.blocked_id) for d in session.exec(select(TodoDependency)).all())


def test_add_creates_edge_and_details_reflect_it(env):
    client, engine = env
    a, b = add_todos(engine, [("a", Status.OPEN), ("b", Status.OPEN)])
    response = client.post(f"/todos/{b}/dependencies", data={"blocker_id": a})
    assert response.status_code == 201
    assert response.json() == {"success": True, "blocker_id": a, "blocked_id": b}
    assert edges(engine) == [(a, b)]
    details = client.get(f"/todos/{b}/details").json()
    assert details["blocked_by"] == [{"id": a, "description": "a", "status": "open"}]
    assert details["blocker_candidates"] == []


def test_remove_deletes_only_that_edge(env):
    client, engine = env
    a, b, c = add_todos(engine, [("a", Status.OPEN), ("b", Status.OPEN), ("c", Status.OPEN)])
    add_edges(engine, [(a, c), (b, c)])
    response = client.delete(f"/todos/{c}/dependencies/{a}")
    assert response.status_code == 200
    assert response.json() == {"success": True}
    assert edges(engine) == [(b, c)]


def test_remove_missing_edge_is_404(env):
    client, engine = env
    a, b = add_todos(engine, [("a", Status.OPEN), ("b", Status.OPEN)])
    response = client.delete(f"/todos/{b}/dependencies/{a}")
    assert response.status_code == 404
    assert response.json() == {"detail": f"No dependency found where #{a} blocks #{b}"}


def test_self_link_is_422(env):
    client, engine = env
    (a,) = add_todos(engine, [("a", Status.OPEN)])
    response = client.post(f"/todos/{a}/dependencies", data={"blocker_id": a})
    assert response.status_code == 422
    assert response.json() == {"detail": "A todo item cannot block itself."}
    assert edges(engine) == []


def test_duplicate_is_422(env):
    client, engine = env
    a, b = add_todos(engine, [("a", Status.OPEN), ("b", Status.OPEN)])
    add_edges(engine, [(a, b)])
    response = client.post(f"/todos/{b}/dependencies", data={"blocker_id": a})
    assert response.status_code == 422
    assert response.json() == {"detail": f"Dependency already exists: #{a} blocks #{b}"}
    assert edges(engine) == [(a, b)]


def test_cycle_is_422(env):
    client, engine = env
    a, b, c = add_todos(engine, [("a", Status.OPEN), ("b", Status.OPEN), ("c", Status.OPEN)])
    add_edges(engine, [(a, b), (b, c)])
    response = client.post(f"/todos/{a}/dependencies", data={"blocker_id": c})
    assert response.status_code == 422
    assert response.json() == {
        "detail": (
            f"Adding this dependency would create a circular dependency: "
            f"#{a} already blocks #{c} (directly or transitively)."
        )
    }
    assert edges(engine) == [(a, b), (b, c)]


def test_missing_blocker_and_missing_blocked_are_404(env):
    client, engine = env
    (a,) = add_todos(engine, [("a", Status.OPEN)])
    response = client.post(f"/todos/{a}/dependencies", data={"blocker_id": 999})
    assert response.status_code == 404
    assert response.json() == {"detail": "Todo item with ID 999 (blocker) not found."}
    response = client.post("/todos/998/dependencies", data={"blocker_id": a})
    assert response.status_code == 404
    assert response.json() == {"detail": "Todo item with ID 998 (blocked) not found."}
    assert edges(engine) == []


def test_candidates_exclude_self_and_existing_blockers(env):
    client, engine = env
    a, b, c = add_todos(engine, [("a", Status.OPEN), ("b", Status.DONE), (HOSTILE, Status.OPEN)])
    add_edges(engine, [(a, b)])
    candidates = client.get(f"/todos/{b}/details").json()["blocker_candidates"]
    assert candidates == [{"id": c, "description": HOSTILE, "status": "open"}]


@pytest.mark.skipif(shutil.which("node") is None, reason="node is required to execute the modal renderer")
def test_modal_has_labelled_picker_and_per_blocker_remove_controls(env):
    client, engine = env
    a, b, c = add_todos(engine, [("a", Status.OPEN), (HOSTILE, Status.OPEN), ("c", Status.OPEN)])
    add_edges(engine, [(a, c)])
    markup = _render(client, client.get(f"/todos/{c}/details").json())
    soup = BeautifulSoup(markup, "html.parser")
    assert "<img" not in markup
    picker = soup.find("select", id="blockerPicker")
    assert soup.find("label", attrs={"for": "blockerPicker"}) is not None
    assert [o["value"] for o in picker.find_all("option")] == ["", str(b)]
    assert picker.find_all("option")[1].get_text() == f"#{b} {HOSTILE}"
    remove = soup.find("button", attrs={"aria-label": f"Remove blocker #{a}"})
    assert remove["onclick"] == f"removeBlocker({c}, {a})"
    assert soup.find("button", string="Add")["onclick"] == f"addBlocker({c})"
    assert soup.find(id="detailDependencyMessage")["role"] == "status"
