#!/usr/bin/env python3
"""
Comprehensive test suite for the Makefile MCP Server

Tests Makefile parsing, target filtering, tool creation, and command execution.
"""

import pytest
import tempfile
import os
import pathlib
from unittest.mock import patch, MagicMock
import subprocess

# Import the makefile MCP components
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


class TestMakefileParser:
    """Test the MakefileParser class functionality."""

    def test_simple_makefile_parsing(self):
        """Test parsing a simple Makefile with basic targets."""
        from makefile_mcp import MakefileParser

        makefile_content = """# Build the project
build:
	echo "Building..."

# Run tests
test:
	pytest

# Clean up build artifacts  
clean:
	rm -rf build/

.PHONY: build test clean
"""

        with tempfile.NamedTemporaryFile(mode="w", suffix=".mk", delete=False) as f:
            f.write(makefile_content)
            makefile_path = f.name

        try:
            parser = MakefileParser(pathlib.Path(makefile_path))
            targets = parser.get_targets()

            assert len(targets) == 3
            assert "build" in targets
            assert "test" in targets
            assert "clean" in targets
            assert targets["build"] == "Build the project"
            assert targets["test"] == "Run tests"
            assert targets["clean"] == "Clean up build artifacts"

        finally:
            os.unlink(makefile_path)

    def test_targets_without_comments(self):
        """Test parsing targets that don't have comment descriptions."""
        from makefile_mcp import MakefileParser

        makefile_content = """build:
	echo "Building..."

# This is a test target
test:
	pytest

install:
	pip install -e .
"""

        with tempfile.NamedTemporaryFile(mode="w", suffix=".mk", delete=False) as f:
            f.write(makefile_content)
            makefile_path = f.name

        try:
            parser = MakefileParser(pathlib.Path(makefile_path))
            targets = parser.get_targets()

            assert targets["build"] == "Execute the 'build' target"  # Default description
            assert targets["test"] == "This is a test target"  # From comment
            assert targets["install"] == "Execute the 'install' target"  # Default description

        finally:
            os.unlink(makefile_path)

    def test_special_targets_ignored(self):
        """Test that special targets (.PHONY, patterns) are ignored."""
        from makefile_mcp import MakefileParser

        makefile_content = """.PHONY: all clean
.DEFAULT_GOAL := all

all:
	echo "All"

%.o: %.c
	gcc -c $< -o $@

clean:
	rm -f *.o

.SUFFIXES: .c .o
"""

        with tempfile.NamedTemporaryFile(mode="w", suffix=".mk", delete=False) as f:
            f.write(makefile_content)
            makefile_path = f.name

        try:
            parser = MakefileParser(pathlib.Path(makefile_path))
            targets = parser.get_targets()

            # Should only include regular targets
            assert len(targets) == 2
            assert "all" in targets
            assert "clean" in targets

            # Special targets should be excluded
            assert ".PHONY" not in targets
            assert ".DEFAULT_GOAL" not in targets
            assert "%.o" not in targets
            assert ".SUFFIXES" not in targets

        finally:
            os.unlink(makefile_path)

    def test_filtering_targets(self):
        """Test include/exclude filtering of targets."""
        from makefile_mcp import MakefileParser

        makefile_content = """build:
\techo "Building..."

test:
\tpytest

clean:
\trm -rf build/

deploy:
\techo "Deploying..."

format:
\tblack .
"""

        with tempfile.NamedTemporaryFile(mode="w", suffix=".mk", delete=False) as f:
            f.write(makefile_content)
            makefile_path = f.name

        try:
            parser = MakefileParser(pathlib.Path(makefile_path))

            # Test include filter
            include_set = {"build", "test"}
            filtered = parser.get_filtered_targets(include_set, set())
            assert len(filtered) == 2
            assert "build" in filtered
            assert "test" in filtered
            assert "clean" not in filtered

            # Test exclude filter
            exclude_set = {"deploy", "format"}
            filtered = parser.get_filtered_targets(None, exclude_set)
            assert len(filtered) == 3
            assert "build" in filtered
            assert "test" in filtered
            assert "clean" in filtered
            assert "deploy" not in filtered
            assert "format" not in filtered

            # Test both include and exclude
            include_set = {"build", "test", "deploy"}
            exclude_set = {"deploy"}
            filtered = parser.get_filtered_targets(include_set, exclude_set)
            assert len(filtered) == 2
            assert "build" in filtered
            assert "test" in filtered
            assert "deploy" not in filtered

        finally:
            os.unlink(makefile_path)

    def test_complex_makefile_parsing(self):
        """Test parsing a more complex, realistic Makefile."""
        from makefile_mcp import MakefileParser

        makefile_content = """# Development Makefile for Python project

# Set up development environment
setup:
\tpython -m venv venv
\t. venv/bin/activate && pip install -e .[dev]

# Install dependencies
install:
\tpip install -e .

# Run linting checks
lint:
\truff check --fix .
\tmypy src/

# Format code  
format:
\truff format .
\tisort src/

# Run the test suite
test:
\tpytest tests/ -v

# Run tests with coverage
test-coverage:
\tpytest tests/ --cov=src --cov-report=html

# Build the package
build: clean
\tpython -m build

# Clean build artifacts
clean:
\trm -rf dist/ build/ *.egg-info/
\tfind . -name __pycache__ -exec rm -rf {} +

# Deploy to PyPI
deploy: build
\ttwine upload dist/*

.PHONY: setup install lint format test test-coverage build clean deploy
"""

        with tempfile.NamedTemporaryFile(mode="w", suffix=".mk", delete=False) as f:
            f.write(makefile_content)
            makefile_path = f.name

        try:
            parser = MakefileParser(pathlib.Path(makefile_path))
            targets = parser.get_targets()

            expected_targets = {
                "setup": "Set up development environment",
                "install": "Install dependencies",
                "lint": "Run linting checks",
                "format": "Format code",
                "test": "Run the test suite",
                "test-coverage": "Run tests with coverage",
                "build": "Build the package",
                "clean": "Clean build artifacts",
                "deploy": "Deploy to PyPI",
            }

            assert len(targets) == len(expected_targets)
            for target, expected_desc in expected_targets.items():
                assert target in targets
                assert targets[target] == expected_desc

        finally:
            os.unlink(makefile_path)


class TestMakefileMCPServer:
    """Test the MCP server functionality."""

    @pytest.fixture
    def test_makefile(self):
        """Create a test Makefile for testing."""
        makefile_content = """# Build the project
build:
\techo "Building project..."

# Run tests
test:
\techo "Running tests..."

# Clean up
clean:
\techo "Cleaning up..."

.PHONY: build test clean
"""

        with tempfile.NamedTemporaryFile(mode="w", suffix=".mk", delete=False) as f:
            f.write(makefile_content)
            f.flush()  # Ensure content is written to disk
            yield f.name

        os.unlink(f.name)

    def test_make_tool_creation(self, test_makefile):
        """Test that make tools are created correctly."""
        # Mock the CLI args and reimport
        with patch("sys.argv", ["makefile_mcp.py", "--makefile", test_makefile]):
            # Clear the module cache
            if "makefile_mcp" in sys.modules:
                del sys.modules["makefile_mcp"]

            import makefile_mcp

            # Manually trigger target parsing with the test makefile
            makefile_mcp.MAKEFILE_PATH = pathlib.Path(test_makefile)
            makefile_mcp.WORKING_DIR = pathlib.Path(test_makefile).parent
            makefile_mcp.INCLUDE_TARGETS = None  # Include all targets
            makefile_mcp.EXCLUDE_TARGETS = set()  # Exclude nothing
            makefile_mcp.filtered_targets = makefile_mcp.get_makefile_targets()

            # Check that targets were parsed
            assert len(makefile_mcp.filtered_targets) == 3
            assert "build" in makefile_mcp.filtered_targets
            assert "test" in makefile_mcp.filtered_targets
            assert "clean" in makefile_mcp.filtered_targets

    @patch("subprocess.run")
    def test_make_tool_execution_success(self, mock_run, test_makefile):
        """Test successful execution of a make target."""
        # Mock successful subprocess execution
        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = "Building project...\n"
        mock_result.stderr = ""
        mock_run.return_value = mock_result

        with patch("sys.argv", ["makefile_mcp.py", "--makefile", test_makefile]):
            if "makefile_mcp" in sys.modules:
                del sys.modules["makefile_mcp"]

            import makefile_mcp

            # Create a make tool for testing
            make_tool = makefile_mcp.create_make_tool("build", "Build the project")

            # Execute the tool
            result = make_tool()

            assert result["status"] == "success"
            assert result["target"] == "build"
            assert result["exit_code"] == 0
            assert result["stdout"] == "Building project...\n"
            assert "Successfully executed target 'build'" in result["message"]

            # Verify subprocess was called correctly
            mock_run.assert_called_once()
            call_args = mock_run.call_args[0][0]
            assert "make" in call_args
            assert "build" in call_args

    @patch("subprocess.run")
    def test_make_tool_execution_failure(self, mock_run, test_makefile):
        """Test failed execution of a make target."""
        # Mock failed subprocess execution
        mock_result = MagicMock()
        mock_result.returncode = 2
        mock_result.stdout = ""
        mock_result.stderr = "make: *** No rule to make target 'invalid'. Stop.\n"
        mock_run.return_value = mock_result

        with patch("sys.argv", ["makefile_mcp.py", "--makefile", test_makefile]):
            if "makefile_mcp" in sys.modules:
                del sys.modules["makefile_mcp"]

            import makefile_mcp

            make_tool = makefile_mcp.create_make_tool("invalid", "Invalid target")
            result = make_tool()

            assert result["status"] == "error"
            assert result["target"] == "invalid"
            assert result["exit_code"] == 2
            assert "failed with exit code 2" in result["message"]

    @patch("subprocess.run")
    def test_make_tool_dry_run(self, mock_run, test_makefile):
        """Test dry run execution of a make target."""
        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = 'echo "Building project..."\n'
        mock_result.stderr = ""
        mock_run.return_value = mock_result

        with patch("sys.argv", ["makefile_mcp.py", "--makefile", test_makefile]):
            if "makefile_mcp" in sys.modules:
                del sys.modules["makefile_mcp"]

            import makefile_mcp

            make_tool = makefile_mcp.create_make_tool("build", "Build the project")
            result = make_tool(dry_run=True)

            assert result["status"] == "success"
            assert result["note"] == "This was a dry run - no commands were actually executed"

            # Verify -n flag was added for dry run
            call_args = mock_run.call_args[0][0]
            assert "-n" in call_args

    @patch("subprocess.run")
    def test_make_tool_with_additional_args(self, mock_run, test_makefile):
        """Test make tool execution with additional arguments."""
        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = "Running tests with verbose output...\n"
        mock_result.stderr = ""
        mock_run.return_value = mock_result

        with patch("sys.argv", ["makefile_mcp.py", "--makefile", test_makefile]):
            if "makefile_mcp" in sys.modules:
                del sys.modules["makefile_mcp"]

            import makefile_mcp

            make_tool = makefile_mcp.create_make_tool("test", "Run tests")
            result = make_tool(additional_args="-j4 VERBOSE=1")

            assert result["status"] == "success"

            call_args = mock_run.call_args[0][0]
            assert "-j4" in call_args
            assert "VERBOSE=1" in call_args

    def test_list_available_targets_tool(self, test_makefile):
        """Test the list_available_targets tool."""
        with patch("sys.argv", ["makefile_mcp.py", "--makefile", test_makefile]):
            if "makefile_mcp" in sys.modules:
                del sys.modules["makefile_mcp"]

            import makefile_mcp

            # Manually trigger target parsing with the test makefile
            makefile_mcp.MAKEFILE_PATH = pathlib.Path(test_makefile)
            makefile_mcp.WORKING_DIR = pathlib.Path(test_makefile).parent
            makefile_mcp.INCLUDE_TARGETS = None  # Include all targets
            makefile_mcp.EXCLUDE_TARGETS = set()  # Exclude nothing
            makefile_mcp.filtered_targets = makefile_mcp.get_makefile_targets()

            result = makefile_mcp.list_available_targets()

            assert "makefile_path" in result
            assert "working_directory" in result
            assert "available_targets" in result
            assert result["available_targets"] == 3
            assert "targets" in result

            target_names = [t["name"] for t in result["targets"]]
            assert "build" in target_names
            assert "test" in target_names
            assert "clean" in target_names

    def test_get_makefile_info_tool(self, test_makefile):
        """Test the get_makefile_info tool."""
        with patch("sys.argv", ["makefile_mcp.py", "--makefile", test_makefile]):
            if "makefile_mcp" in sys.modules:
                del sys.modules["makefile_mcp"]

            import makefile_mcp

            # Manually trigger target parsing with the test makefile
            makefile_mcp.MAKEFILE_PATH = pathlib.Path(test_makefile)
            makefile_mcp.WORKING_DIR = pathlib.Path(test_makefile).parent
            makefile_mcp.INCLUDE_TARGETS = None  # Include all targets
            makefile_mcp.EXCLUDE_TARGETS = set()  # Exclude nothing
            makefile_mcp.filtered_targets = makefile_mcp.get_makefile_targets()

            result = makefile_mcp.get_makefile_info()

            assert result["makefile_exists"] is True
            assert result["all_targets"]["count"] == 3
            assert result["filtered_targets"]["count"] == 3
            assert result["filters"]["include"] is None
            assert result["filters"]["exclude"] is None


class TestCommandLineArguments:
    """Test command-line argument parsing and filtering."""

    def test_include_filter(self):
        """Test --include command line argument."""
        test_args = ["makefile_mcp.py", "--include", "build,test"]

        with patch("sys.argv", test_args):
            if "makefile_mcp" in sys.modules:
                del sys.modules["makefile_mcp"]

            # Just test the arg parsing function directly
            from makefile_mcp import parse_cli_args

            args = parse_cli_args()

            assert args.include == "build,test"
            assert args.exclude is None

    def test_exclude_filter(self):
        """Test --exclude command line argument."""
        test_args = ["makefile_mcp.py", "--exclude", "clean,deploy"]

        with patch("sys.argv", test_args):
            if "makefile_mcp" in sys.modules:
                del sys.modules["makefile_mcp"]

            from makefile_mcp import parse_cli_args

            args = parse_cli_args()

            assert args.exclude == "clean,deploy"
            assert args.include is None

    def test_custom_makefile_path(self):
        """Test --makefile command line argument."""
        test_args = ["makefile_mcp.py", "--makefile", "/custom/path/Makefile"]

        with patch("sys.argv", test_args):
            if "makefile_mcp" in sys.modules:
                del sys.modules["makefile_mcp"]

            from makefile_mcp import parse_cli_args

            args = parse_cli_args()

            assert args.makefile == "/custom/path/Makefile"

    def test_working_directory(self):
        """Test --working-dir command line argument."""
        test_args = ["makefile_mcp.py", "--working-dir", "/custom/work/dir"]

        with patch("sys.argv", test_args):
            if "makefile_mcp" in sys.modules:
                del sys.modules["makefile_mcp"]

            from makefile_mcp import parse_cli_args

            args = parse_cli_args()

            assert args.working_dir == "/custom/work/dir"


class TestErrorHandling:
    """Test error handling scenarios."""

    @patch("subprocess.run")
    def test_subprocess_timeout(self, mock_run):
        """Test handling of subprocess timeout."""
        mock_run.side_effect = subprocess.TimeoutExpired("make", 300)

        # Create a temporary makefile for this test
        makefile_content = "test:\n\techo 'test'"
        with tempfile.NamedTemporaryFile(mode="w", suffix=".mk", delete=False) as f:
            f.write(makefile_content)
            makefile_path = f.name

        try:
            with patch("sys.argv", ["makefile_mcp.py", "--makefile", makefile_path]):
                if "makefile_mcp" in sys.modules:
                    del sys.modules["makefile_mcp"]

                import makefile_mcp

                make_tool = makefile_mcp.create_make_tool("test", "Test target")
                result = make_tool()

                assert result["status"] == "error"
                assert "timed out" in result["message"]
                assert result["exit_code"] == -1
        finally:
            os.unlink(makefile_path)

    @patch("subprocess.run")
    def test_subprocess_error(self, mock_run):
        """Test handling of subprocess errors."""
        mock_run.side_effect = subprocess.SubprocessError("Command failed")

        makefile_content = "test:\n\techo 'test'"
        with tempfile.NamedTemporaryFile(mode="w", suffix=".mk", delete=False) as f:
            f.write(makefile_content)
            makefile_path = f.name

        try:
            with patch("sys.argv", ["makefile_mcp.py", "--makefile", makefile_path]):
                if "makefile_mcp" in sys.modules:
                    del sys.modules["makefile_mcp"]

                import makefile_mcp

                make_tool = makefile_mcp.create_make_tool("test", "Test target")
                result = make_tool()

                assert result["status"] == "error"
                assert "Failed to execute" in result["message"]
                assert result["exit_code"] == -1
        finally:
            os.unlink(makefile_path)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
