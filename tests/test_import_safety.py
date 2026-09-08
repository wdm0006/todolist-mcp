"""Import-safety contract: importing todo_mcp must have no side effects.

The server used to parse CLI arguments and create a database engine at import time,
which broke embedding the module and collapsed mutation campaigns (any mutant that
broke import failed the whole suite at collection). Runs in a fresh interpreter so
the lazy-initialization contract cannot regress silently.
"""

import pathlib
import subprocess
import sys

PROJECT_ROOT = pathlib.Path(__file__).resolve().parent.parent

PROBE = """
import sys
sys.path.insert(0, {root!r})
import todo_mcp

assert todo_mcp.engine is None, "database engine created at import time"
info = todo_mcp.get_cli_args.cache_info()
assert info.currsize == 0, "CLI arguments parsed at import time"
print("ok")
"""


def test_import_has_no_side_effects():
    result = subprocess.run(  # noqa: S603 — PROBE is a static string, not untrusted input
        [sys.executable, "-c", PROBE.format(root=str(PROJECT_ROOT))],
        capture_output=True,
        text=True,
        cwd=str(PROJECT_ROOT),
    )
    assert result.returncode == 0, result.stderr
    # stdout must be exactly the probe marker: importing the module emits nothing
    # (stray stdout would corrupt the stdio MCP protocol).
    assert result.stdout.strip() == "ok"


def test_get_engine_creates_engine_lazily():
    """get_engine() initializes the module engine exactly once, on first use."""
    import todo_mcp

    assert todo_mcp.engine is None  # untouched by the import above
    try:
        engine = todo_mcp.get_engine()
        assert todo_mcp.engine is engine
    finally:
        todo_mcp.engine = None  # do not leak the default engine into other tests
