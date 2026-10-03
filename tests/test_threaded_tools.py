"""Live protocol tests: database-backed tools run off the FastMCP event-loop thread."""

import asyncio
import os
import tempfile
import threading
import time

import pytest
from fastmcp import Client
from sqlmodel import SQLModel, create_engine

import todo_mcp
from todo_mcp import get_item_by_id, mcp_server

DB_TOOLS = {
    "add_item",
    "get_item_by_id",
    "list_items",
    "update_item",
    "mark_item_done",
    "remove_item",
    "add_dependency",
    "remove_dependency",
    "list_dependencies",
    "get_ready_items",
    "get_dependency_chain",
}


@pytest.fixture
def temp_db(monkeypatch):
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as tf:
        db_url = f"sqlite:///{tf.name}"
    test_engine = create_engine(db_url)
    SQLModel.metadata.create_all(test_engine)
    monkeypatch.setattr("todo_mcp.engine", test_engine)
    yield test_engine
    os.unlink(tf.name)


def test_module_functions_stay_synchronous():
    assert not asyncio.iscoroutinefunction(get_item_by_id)
    assert get_item_by_id.__module__ == "todo_mcp"


def test_tools_list_schemas_match_function_signatures():
    async def run():
        async with Client(mcp_server) as client:
            return {t.name: t.inputSchema for t in await client.list_tools()}

    schemas = asyncio.run(run())
    assert set(schemas) == DB_TOOLS | {"assistant_workflow_guide"}
    assert set(schemas["add_item"]["properties"]) == {
        "description",
        "long_description",
        "priority",
        "due_date_str",
        "tags",
    }
    assert schemas["get_item_by_id"]["required"] == ["item_id"]
    assert schemas["get_item_by_id"]["properties"]["item_id"]["type"] == "integer"


def test_tool_call_returns_same_result_through_protocol(temp_db):
    async def run():
        async with Client(mcp_server) as client:
            created = await client.call_tool("add_item", {"description": "via protocol"})
            fetched = await client.call_tool("get_item_by_id", {"item_id": created.data["id"]})
            return fetched.data

    assert asyncio.run(run())["description"] == "via protocol"


def test_ping_answered_while_slow_tool_call_is_in_flight(temp_db, monkeypatch):
    real_get_engine = todo_mcp.get_engine
    release = threading.Event()
    entered = threading.Event()
    tool_threads = []

    def slow_get_engine():
        tool_threads.append(threading.current_thread())
        entered.set()
        release.wait(timeout=5)
        return real_get_engine()

    monkeypatch.setattr(todo_mcp, "get_engine", slow_get_engine)

    async def run():
        loop_thread = threading.current_thread()
        async with Client(mcp_server) as client:
            slow = asyncio.create_task(client.call_tool("get_item_by_id", {"item_id": 1}))
            while not entered.is_set():
                await asyncio.sleep(0.01)
            started = time.monotonic()
            await asyncio.wait_for(client.ping(), timeout=3)
            ping_elapsed = time.monotonic() - started
            slow_done_at_ping = slow.done()
            release.set()
            result = await slow
            return loop_thread, ping_elapsed, slow_done_at_ping, result

    loop_thread, ping_elapsed, slow_done_at_ping, result = asyncio.run(run())
    assert not slow_done_at_ping
    assert ping_elapsed < 3
    assert tool_threads and tool_threads[0] is not loop_thread
    assert result.data["error"]
