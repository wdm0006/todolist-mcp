# ruff: noqa: S603, S607
import os
import shutil
import subprocess
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parent.parent

pytestmark = pytest.mark.skipif(
    shutil.which("make") is None or shutil.which("uv") is None, reason="make and uv are required"
)


def _make(*args: str, env: dict) -> list[str]:
    result = subprocess.run(["make", "-n", "-C", str(REPO), *args], capture_output=True, text=True, env=env, check=True)
    return result.stdout.splitlines()


def test_install_recipe_is_idempotent_and_pins_interpreter():
    env = {k: v for k, v in os.environ.items() if k != "VIRTUAL_ENV"}
    lines = _make("install", env=env)
    venv_line = next(line for line in lines if "venv" in line)
    pip_line = next(line for line in lines if "pip install" in line)
    assert venv_line.startswith("test -x .venv/bin/python ||")
    assert "--python .venv/bin/python" in pip_line


def test_install_twice_with_foreign_virtual_env(tmp_path):
    """Run the real recipe in a copy of the repo metadata twice; VIRTUAL_ENV must not redirect it."""
    work = tmp_path / "proj"
    work.mkdir()
    for name in ("Makefile", "pyproject.toml", "README.md", "todo_mcp.py", "utc_timestamp.py", "kanban_web.py"):
        if (REPO / name).exists():
            shutil.copy(REPO / name, work / name)
    foreign = tmp_path / "foreign"
    subprocess.run(["uv", "venv", str(foreign)], check=True, capture_output=True)
    env = {**os.environ, "VIRTUAL_ENV": str(foreign)}
    for _ in range(2):
        subprocess.run(["make", "-C", str(work), "install"], check=True, capture_output=True, env=env)
    probe = "import fastapi, pytest, fastmcp"
    subprocess.run([str(work / ".venv/bin/python"), "-c", probe], check=True)
    foreign_probe = subprocess.run([str(foreign / "bin/python"), "-c", "import fastmcp"], capture_output=True)
    assert foreign_probe.returncode != 0
