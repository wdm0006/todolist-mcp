"""Read-only dependency lists in GET /todos/{id}/details and the detail modal."""

import json
import os
import shutil
import subprocess
import sys

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import event
from sqlmodel import Session, SQLModel, create_engine

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import kanban_web  # noqa: E402
from kanban_web import Status, Todo, TodoDependency  # noqa: E402
from test_kanban_web_escaping import extract_js_function  # noqa: E402

HOSTILE = '<img src=x onerror="alert(1)">'


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


def add_todos(engine, specs):
    with Session(engine) as session:
        todos = [Todo(description=d, status=s) for d, s in specs]
        session.add_all(todos)
        session.commit()
        return [t.id for t in todos]


def add_edges(engine, edges):
    with Session(engine) as session:
        session.add_all(TodoDependency(blocker_id=a, blocked_id=b) for a, b in edges)
        session.commit()


def test_details_lists_both_directions_with_exact_values(env):
    client, engine = env
    up2, up1, mid, down1, down2, loner = add_todos(
        engine,
        [
            ("up2", Status.DONE),
            ("up1", Status.IN_PROGRESS),
            ("mid", Status.OPEN),
            ("down1", Status.CANCELLED),
            (HOSTILE, Status.OPEN),
            ("loner", Status.OPEN),
        ],
    )
    add_edges(engine, [(up2, mid), (up1, mid), (mid, down1), (mid, down2), (up1, loner)])

    body = client.get(f"/todos/{mid}/details").json()
    assert body["blocked_by"] == [
        {"id": up2, "description": "up2", "status": "done"},
        {"id": up1, "description": "up1", "status": "in_progress"},
    ]
    assert body["blocks"] == [
        {"id": down1, "description": "down1", "status": "cancelled"},
        {"id": down2, "description": HOSTILE, "status": "open"},
    ]


def test_details_without_edges_returns_empty_lists(env):
    client, engine = env
    (solo,) = add_todos(engine, [("solo", Status.OPEN)])
    body = client.get(f"/todos/{solo}/details").json()
    assert body["blocked_by"] == [] and body["blocks"] == []


def _count_details_queries(client, engine, todo_id):
    statements = []

    def record(conn, cursor, statement, parameters, context, executemany):
        statements.append(statement)

    event.listen(engine, "before_cursor_execute", record)
    try:
        assert client.get(f"/todos/{todo_id}/details").status_code == 200
    finally:
        event.remove(engine, "before_cursor_execute", record)
    return len(statements)


def test_details_query_count_is_constant(env):
    client, engine = env
    ids = add_todos(engine, [(f"t{i}", Status.OPEN) for i in range(13)])
    hub, small, wide = ids[0], ids[1:3], ids[3:]
    add_edges(engine, [(small[0], hub), (hub, small[1])])
    few = _count_details_queries(client, engine, hub)
    add_edges(engine, [(w, hub) for w in wide[:5]] + [(hub, w) for w in wide[5:]])
    many = _count_details_queries(client, engine, hub)
    assert many == few


def _render(client, payload):
    page = client.get("/").text
    script = "\n".join(
        [
            extract_js_function(page, "escapeHtml"),
            extract_js_function(page, "populateDetailModal"),
            "let rendered = '';",
            "globalThis.document = { getElementById: () => ({ set innerHTML(v) { rendered = v; } }) };",
            "populateDetailModal(JSON.parse(process.argv[1]));",
            "process.stdout.write(rendered);",
        ]
    )
    return subprocess.run(  # noqa: S603
        [shutil.which("node"), "-e", script, "--", json.dumps(payload)],
        capture_output=True,
        text=True,
        check=True,
    ).stdout


@pytest.mark.skipif(shutil.which("node") is None, reason="node is required to execute the modal renderer")
def test_modal_renders_dependencies_as_text_and_none_when_empty(env):
    client, engine = env
    blocker, mid, empty = add_todos(engine, [(HOSTILE, Status.OPEN), ("mid", Status.OPEN), ("e", Status.OPEN)])
    add_edges(engine, [(blocker, mid)])

    markup = _render(client, client.get(f"/todos/{mid}/details").json())
    assert "<img" not in markup
    assert "&lt;img src=x onerror=&quot;alert(1)&quot;&gt;" in markup
    assert "(open)" in markup
    assert markup.count(">None<") == 1  # "Blocks" is empty, "Blocked by" is not

    markup = _render(client, client.get(f"/todos/{empty}/details").json())
    assert markup.count(">None<") == 2
