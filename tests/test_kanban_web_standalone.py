import shutil
import subprocess
import tempfile
from pathlib import Path

from sqlmodel import SQLModel

import kanban_web
import todo_mcp


REPO_ROOT = Path(__file__).resolve().parents[1]
UV = shutil.which("uv")


def test_standalone_script_loads_shared_schema():
    assert UV is not None
    help_result = subprocess.run(  # noqa: S603
        [UV, "run", "--script", "kanban_web.py", "--help"],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        check=False,
    )

    script = (REPO_ROOT / "kanban_web.py").read_text()
    metadata_end = script.index("# ///", script.index("# ///") + 1) + len("# ///")
    probe = (
        script[:metadata_end]
        + """
import kanban_web
import todo_mcp
from sqlmodel import SQLModel

assert kanban_web.Todo is todo_mcp.Todo
assert kanban_web.Status is todo_mcp.Status
assert kanban_web.Priority is todo_mcp.Priority
assert kanban_web.run_migrations is todo_mcp.run_migrations
assert {"todo", "tododependency"} <= set(SQLModel.metadata.tables)
"""
    )
    with tempfile.NamedTemporaryFile(mode="w", suffix=".py", dir=REPO_ROOT) as probe_file:
        probe_file.write(probe)
        probe_file.flush()
        probe_result = subprocess.run(  # noqa: S603
            [UV, "run", "--script", probe_file.name],
            cwd=REPO_ROOT,
            capture_output=True,
            text=True,
            check=False,
        )

    assert help_result.returncode == 0, help_result.stderr
    assert probe_result.returncode == 0, probe_result.stderr
    assert kanban_web.Todo is todo_mcp.Todo
    assert kanban_web.Status is todo_mcp.Status
    assert kanban_web.Priority is todo_mcp.Priority
    assert {"todo", "tododependency"} <= set(SQLModel.metadata.tables)


def test_setup_database_uses_shared_migrations(tmp_path, monkeypatch):
    calls = []

    assert kanban_web.run_migrations is todo_mcp.run_migrations
    monkeypatch.setattr(kanban_web, "run_migrations", calls.append)

    kanban_web.setup_database(str(tmp_path))

    assert calls == [kanban_web.engine]
