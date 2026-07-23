#!/usr/bin/env python3
"""
Regression tests: persisted todo content must render as text, never as markup.

Covers both rendering boundaries of the kanban web app:
  * the server-generated board fragment (``generate_kanban_html``)
  * the browser detail modal (``populateDetailModal``, executed with node)
"""

import pytest
import json
import os
import shutil
import subprocess
import tempfile
from fastapi.testclient import TestClient
from sqlmodel import SQLModel, Session, create_engine
from bs4 import BeautifulSoup

import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from kanban_web import app, Todo, Status, Priority, get_session  # noqa: E402

HOSTILE_DESCRIPTION = '<img src=x onerror="alert(1)">Fix login'
HOSTILE_LONG_DESCRIPTION = "</div><script>alert('xss')</script>"
HOSTILE_TAGS = '<img src=y onerror=alert(2)>,backend" onmouseover="alert(3)'


@pytest.fixture(scope="function")
def temp_db():
    """Create a temporary database for testing"""
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as temp_file:
        temp_db_path = temp_file.name

    try:
        test_engine = create_engine(f"sqlite:///{temp_db_path}")
        SQLModel.metadata.create_all(test_engine)
        yield test_engine
    finally:
        try:
            os.unlink(temp_db_path)
        except OSError:
            pass


@pytest.fixture(scope="function")
def test_client(temp_db):
    """Create test client with isolated database"""

    def override_get_session():
        with Session(temp_db) as session:
            yield session

    app.dependency_overrides[get_session] = override_get_session

    import kanban_web

    kanban_web.engine = temp_db

    yield TestClient(app), temp_db

    app.dependency_overrides.clear()


@pytest.fixture(scope="function")
def hostile_todo(test_client):
    """Persist a todo whose every text field carries markup"""
    client, engine = test_client

    todo = Todo(
        description=HOSTILE_DESCRIPTION,
        long_description=HOSTILE_LONG_DESCRIPTION,
        priority=Priority.HIGH,
        status=Status.OPEN,
        tags=HOSTILE_TAGS,
    )
    with Session(engine) as session:
        session.add(todo)
        session.commit()
        session.refresh(todo)

    return todo


def assert_inert(markup: str, expected_text: str, allowed_handlers: tuple = ()) -> None:
    """Assert markup contains no injected executable content but still shows the text

    ``allowed_handlers`` lists value prefixes of event handlers the application itself
    renders; any other event handler must have come from the persisted payload.
    """
    soup = BeautifulSoup(markup, "html.parser")

    assert soup.find("img") is None, "hostile payload produced an <img> element"
    assert soup.find("script") is None, "hostile payload produced a <script> element"

    for tag in soup.find_all(True):
        for attribute, value in tag.attrs.items():
            if not attribute.lower().startswith("on"):
                continue
            assert str(value).startswith(allowed_handlers), (
                f"hostile payload produced event handler {attribute}={value}"
            )

    assert expected_text in soup.get_text()


class TestBoardRenderingEscaping:
    """The server-rendered board must escape descriptions and tag labels"""

    @pytest.mark.parametrize("path", ["/", "/kanban-board"])
    def test_hostile_todo_renders_as_text(self, test_client, hostile_todo, path):
        client, _ = test_client

        response = client.get(path)
        assert response.status_code == 200

        soup = BeautifulSoup(response.text, "html.parser")
        card = soup.find("div", class_="todo-card")
        assert card is not None

        # The card's own onclick handler is application markup, not persisted content
        assert_inert(str(card), HOSTILE_DESCRIPTION, allowed_handlers=("showDetailModal(",))
        assert card.find("div", class_="card-title").get_text() == HOSTILE_DESCRIPTION

        tag_labels = [tag.get_text() for tag in card.find_all("span", class_="tag")]
        assert "<img src=y onerror=alert(2)>" in tag_labels
        assert 'backend" onmouseover="alert(3)' in tag_labels


def extract_js_function(page_html: str, name: str) -> str:
    """Extract a top-level JS function body from the served page by brace matching"""
    start = page_html.index(f"function {name}(")
    depth = 0
    for index in range(start, len(page_html)):
        character = page_html[index]
        if character == "{":
            depth += 1
        elif character == "}":
            depth -= 1
            if depth == 0:
                return page_html[start : index + 1]
    raise AssertionError(f"unbalanced braces while extracting {name}")


class TestDetailModalEscaping:
    """The detail modal must insert persisted content as text"""

    def test_source_never_interpolates_raw_todo_text(self, test_client):
        client, _ = test_client
        page = client.get("/").text
        source = extract_js_function(page, "populateDetailModal")

        for field in ("description", "long_description", "priority", "due_date"):
            assert f"${{todo.{field}}}" not in source, f"todo.{field} is interpolated without escaping"
            assert f"escapeHtml(todo.{field})" in source
        assert "${statusLabel}" not in source
        assert "${tag.trim()}" not in source

    @pytest.mark.skipif(shutil.which("node") is None, reason="node is required to execute the modal renderer")
    def test_modal_renders_hostile_content_as_text(self, test_client, hostile_todo):
        client, _ = test_client

        details = client.get(f"/todos/{hostile_todo.id}/details")
        assert details.status_code == 200

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

        result = subprocess.run(  # noqa: S603
            [shutil.which("node"), "-e", script, "--", json.dumps(details.json())],
            capture_output=True,
            text=True,
            check=True,
        )

        markup = result.stdout
        assert_inert(markup, HOSTILE_DESCRIPTION)
        assert_inert(markup, HOSTILE_LONG_DESCRIPTION)
        assert_inert(markup, 'backend" onmouseover="alert(3)')
