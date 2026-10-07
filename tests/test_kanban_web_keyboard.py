"""Keyboard accessibility of the kanban board: focusable cards and a labelled status control in the modal."""

import json
import os
import shutil
import subprocess
import sys

import pytest
from bs4 import BeautifulSoup
from fastapi.testclient import TestClient
from sqlmodel import Session

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from kanban_web import Priority, Status, Todo  # noqa: E402
from sqlmodel import SQLModel, create_engine  # noqa: E402
from test_kanban_web_escaping import extract_js_function  # noqa: E402
import kanban_web  # noqa: E402


@pytest.fixture
def test_client(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path / 'todo.db'}")
    SQLModel.metadata.create_all(engine)

    def override_get_session():
        with Session(engine) as session:
            yield session

    kanban_web.app.dependency_overrides[kanban_web.get_session] = override_get_session
    kanban_web.engine = engine
    yield TestClient(kanban_web.app), engine
    kanban_web.app.dependency_overrides.clear()


@pytest.fixture
def card_todo(test_client):
    _, engine = test_client
    with Session(engine) as session:
        todo = Todo(description="Keyboard task", priority=Priority.LOW, status=Status.OPEN)
        session.add(todo)
        session.commit()
        session.refresh(todo)
    return todo


@pytest.mark.parametrize("path", ["/", "/kanban-board"])
def test_card_is_focusable_button(test_client, card_todo, path):
    client, _ = test_client
    soup = BeautifulSoup(client.get(path).text, "html.parser")
    card = soup.find("div", class_="todo-card")
    assert card["tabindex"] == "0"
    assert card["role"] == "button"
    assert card["onkeydown"] == f"handleCardKeydown(event, {card_todo.id})"
    assert "Keyboard task" in card["aria-label"]


def test_page_has_modal_status_control_and_focus_styles(test_client):
    client, _ = test_client
    page = client.get("/").text
    source = extract_js_function(page, "populateDetailModal")
    assert 'for="detailStatus"' in source
    assert '<select id="detailStatus"' in source
    assert "changeTodoStatus(" in source
    assert ".todo-card:focus-visible" in page
    assert ".todo-card:focus-within .card-actions" in page
    assert 'role="dialog"' in page and 'aria-modal="true"' in page


@pytest.mark.skipif(shutil.which("node") is None, reason="node is required to execute the modal renderer")
def test_modal_select_lists_every_status_and_selects_current(test_client, card_todo):
    client, _ = test_client
    page = client.get("/").text
    details = client.get(f"/todos/{card_todo.id}/details").json()
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
    out = subprocess.run(  # noqa: S603
        [shutil.which("node"), "-e", script, "--", json.dumps(details)],
        capture_output=True,
        text=True,
        check=True,
    ).stdout
    select = BeautifulSoup(out, "html.parser").find("select", id="detailStatus")
    assert [o["value"] for o in select.find_all("option")] == ["open", "in_progress", "done", "cancelled"]
    assert [o["value"] for o in select.find_all("option", selected=True)] == ["open"]


def test_status_endpoint_moves_card_in_board_fragment(test_client, card_todo):
    client, _ = test_client
    assert client.put(f"/todos/{card_todo.id}/status", data={"status": "done"}).status_code == 200
    soup = BeautifulSoup(client.get("/kanban-board").text, "html.parser")
    done = soup.find("div", class_="todo-list", attrs={"data-status": "done"})
    assert done.find("div", class_="todo-card")["data-todo-id"] == str(card_todo.id)
