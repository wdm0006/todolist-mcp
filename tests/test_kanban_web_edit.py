"""Editing task fields from the kanban detail modal: PUT /todos/{id} and the modal's edit form."""

import json
import os
import shutil
import subprocess
import sys
from datetime import date, datetime

import pytest
from bs4 import BeautifulSoup
from fastapi.testclient import TestClient
from sqlmodel import Session, SQLModel, create_engine, select

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import kanban_web  # noqa: E402
from kanban_web import Priority, Status, Todo, TodoDependency  # noqa: E402
from test_kanban_web_escaping import extract_js_function  # noqa: E402

CREATED = datetime(2024, 1, 2, 3, 4, 5)


@pytest.fixture
def env(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path / 'todo.db'}")
    SQLModel.metadata.create_all(engine)

    def override_get_session():
        with Session(engine) as session:
            yield session

    kanban_web.app.dependency_overrides[kanban_web.get_session] = override_get_session
    with Session(engine) as session:
        other = Todo(description="Other")
        todo = Todo(
            description="Original",
            long_description="notes",
            status=Status.IN_PROGRESS,
            priority=Priority.HIGH,
            tags="a,b",
            due_date=date(2030, 1, 1),
            created_at=CREATED,
            updated_at=CREATED,
        )
        session.add(todo)
        session.add(other)
        session.commit()
        session.add(TodoDependency(blocker_id=other.id, blocked_id=todo.id))
        session.commit()
        todo_id, other_id = todo.id, other.id
    yield TestClient(kanban_web.app), engine, todo_id, other_id
    kanban_web.app.dependency_overrides.clear()


def stored(engine, todo_id):
    with Session(engine) as session:
        return session.get(Todo, todo_id)


def edges(engine):
    with Session(engine) as session:
        return [(e.blocker_id, e.blocked_id) for e in session.exec(select(TodoDependency)).all()]


FULL = {
    "description": "  New title  ",
    "long_description": "new notes",
    "priority": "low",
    "tags": "x,y",
    "due_date": "2031-02-03",
}


def test_save_updates_exact_values_and_keeps_other_fields(env):
    client, engine, tid, other = env
    before_edges = edges(engine)
    resp = client.put(f"/todos/{tid}", data=FULL)
    assert resp.status_code == 200
    todo = stored(engine, tid)
    assert (todo.description, todo.long_description, todo.priority, todo.tags, todo.due_date) == (
        "New title",
        "new notes",
        Priority.LOW,
        "x,y",
        date(2031, 2, 3),
    )
    assert todo.status == Status.IN_PROGRESS
    assert todo.created_at == CREATED
    assert todo.updated_at > CREATED
    assert edges(engine) == before_edges
    body = resp.json()
    assert body["description"] == "New title" and body["due_date"] == "2031-02-03" and body["status"] == "in_progress"


def test_blank_optional_fields_clear_to_null(env):
    client, engine, tid, _ = env
    raw = "description=Keep&priority=medium&long_description=&tags=&due_date="
    resp = client.put(f"/todos/{tid}", content=raw, headers={"Content-Type": "application/x-www-form-urlencoded"})
    assert resp.status_code == 200
    todo = stored(engine, tid)
    assert (todo.long_description, todo.tags, todo.due_date) == (None, None, None)
    assert todo.description == "Keep" and todo.priority == Priority.MEDIUM


def test_omitted_optional_fields_clear_too(env):
    client, engine, tid, _ = env
    assert client.put(f"/todos/{tid}", data={"description": "D", "priority": "high"}).status_code == 200
    todo = stored(engine, tid)
    assert (todo.long_description, todo.tags, todo.due_date) == (None, None, None)


@pytest.mark.parametrize(
    "override",
    [
        {"description": "   "},
        {"due_date": "2031-13-45"},
        {"due_date": "tomorrow"},
        {"priority": "urgent"},
        {"priority": ""},
    ],
)
def test_invalid_submission_changes_nothing_even_with_valid_title(env, override):
    client, engine, tid, _ = env
    snapshot = stored(engine, tid).model_dump()
    data = {**FULL, "description": "Valid changed title", **override}
    resp = client.put(f"/todos/{tid}", data=data)
    assert resp.status_code == 422
    assert stored(engine, tid).model_dump() == snapshot


def test_missing_task_returns_404(env):
    client, engine, _, _ = env
    assert client.put("/todos/9999", data=FULL).status_code == 404
    assert client.put("/todos/9999", data={**FULL, "description": " "}).status_code == 404


def test_edit_writes_to_injected_session_database(env, tmp_path):
    client, engine, tid, _ = env
    other_engine = create_engine(f"sqlite:///{tmp_path / 'elsewhere.db'}")
    SQLModel.metadata.create_all(other_engine)
    client.put(f"/todos/{tid}", data=FULL)
    with Session(other_engine) as session:
        assert session.exec(select(Todo)).all() == []


def test_hostile_text_round_trips_and_board_escapes_it(env):
    client, engine, tid, _ = env
    hostile = '<img src=x onerror="alert(1)"> "q" \'s\''
    assert client.put(f"/todos/{tid}", data={**FULL, "description": hostile, "tags": "<b>t</b>"}).status_code == 200
    assert stored(engine, tid).description == hostile
    assert client.get(f"/todos/{tid}/details").json()["description"] == hostile
    soup = BeautifulSoup(client.get("/kanban-board").text, "html.parser")
    assert soup.find("img") is None and soup.find("b") is None


def test_page_has_edit_affordance(env):
    client, *_ = env
    page = client.get("/").text
    populate = extract_js_function(page, "populateDetailModal")
    assert 'id="detailEditButton"' in populate and "showEditForm()" in populate
    form = extract_js_function(page, "showEditForm")
    for label_for in ("editDescription", "editLongDescription", "editPriority", "editTags", "editDueDate"):
        assert f'for="{label_for}"' in form
    assert 'role="alert"' in form
    assert "disabled = true" in extract_js_function(page, "submitEdit")


@pytest.mark.skipif(shutil.which("node") is None, reason="node is required to execute the edit form")
def test_edit_form_prepopulates_and_keeps_hostile_values_as_text(env):
    client, engine, tid, _ = env
    hostile = '"><script>alert(1)</script>'
    client.put(f"/todos/{tid}", data={**FULL, "description": hostile, "tags": hostile, "long_description": hostile})
    page = client.get("/").text
    details = client.get(f"/todos/{tid}/details").json()
    script = "\n".join(
        [
            extract_js_function(page, "escapeHtml"),
            extract_js_function(page, "showEditForm"),
            "let rendered = '';",
            "const el = { focus() {}, set innerHTML(v) { rendered = v; } };",
            "globalThis.document = { getElementById: () => el };",
            "globalThis.detailTodo = JSON.parse(process.argv[1]);",
            "showEditForm();",
            "process.stdout.write(rendered);",
        ]
    )
    out = subprocess.run(  # noqa: S603
        [shutil.which("node"), "-e", script, "--", json.dumps(details)],
        capture_output=True,
        text=True,
        check=True,
    ).stdout
    soup = BeautifulSoup(out, "html.parser")
    assert soup.find("script") is None
    assert soup.find("textarea", id="editDescription").text == hostile
    assert soup.find("input", id="editTags")["value"] == hostile
    assert soup.find("input", id="editDueDate")["value"] == "2031-02-03"
    assert [o["value"] for o in soup.find("select", id="editPriority").find_all("option", selected=True)] == ["low"]
