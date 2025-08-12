#!/usr/bin/env python3
# /// script
# dependencies = [
#   "mcp[cli]>=1.7.0,<2.0.0"
# ]
# ///

"""
Makefile MCP Server

A Model Context Protocol (MCP) server that exposes Makefile targets as tools.
AI assistants can discover and execute make targets through this server.

Usage: uv run makefile_mcp.py [--makefile PATH] [--include TARGET1,TARGET2] [--exclude TARGET1,TARGET2]
"""

import argparse
import os
import pathlib
import re
import subprocess
import sys
from typing import Dict, Optional, Set, Any

from mcp.server.fastmcp import FastMCP

# Global variables
MAKEFILE_PATH = None
WORKING_DIR = None


def parse_cli_args():
    """
    Parse command-line arguments for Makefile configuration.
    Returns:
        argparse.Namespace: Parsed arguments.
    """
    parser = argparse.ArgumentParser(description="Makefile MCP Server")
    parser.add_argument(
        "--makefile", type=str, default="Makefile", help="Path to the Makefile (default: Makefile in current directory)"
    )
    parser.add_argument("--include", type=str, help="Comma-separated list of targets to include (default: all targets)")
    parser.add_argument("--exclude", type=str, help="Comma-separated list of targets to exclude")
    parser.add_argument(
        "--working-dir", type=str, help="Working directory for make commands (default: directory containing Makefile)"
    )
    parser.add_argument(
        "--max-output-tokens",
        type=int,
        default=25000,
        help="Maximum number of tokens to return from command output (default: 25000)",
    )

    known_args, _ = parser.parse_known_args()
    return known_args


def initialize_makefile_mcp():
    """Initialize the makefile MCP server with validation."""
    global MAKEFILE_PATH, WORKING_DIR

    # Parse CLI arguments
    cli_args = parse_cli_args()

    # Resolve Makefile path
    if os.path.isabs(cli_args.makefile):
        MAKEFILE_PATH = pathlib.Path(cli_args.makefile)
    else:
        MAKEFILE_PATH = pathlib.Path.cwd() / cli_args.makefile

    if not MAKEFILE_PATH.exists():
        print(f"Error: Makefile not found at {MAKEFILE_PATH}", file=sys.stderr)
        sys.exit(1)

    # Set working directory
    if cli_args.working_dir:
        WORKING_DIR = pathlib.Path(cli_args.working_dir).resolve()
    else:
        WORKING_DIR = MAKEFILE_PATH.parent.resolve()

    if not WORKING_DIR.is_dir():
        print(f"Error: Working directory not found: {WORKING_DIR}", file=sys.stderr)
        sys.exit(1)

    return cli_args


# Initialize only when running as script, not when imported
if __name__ == "__main__":
    cli_args = initialize_makefile_mcp()
else:
    # For imports (like tests), set up defaults without validation
    cli_args = parse_cli_args()
    if os.path.isabs(cli_args.makefile):
        MAKEFILE_PATH = pathlib.Path(cli_args.makefile)
    else:
        MAKEFILE_PATH = pathlib.Path.cwd() / cli_args.makefile

    if cli_args.working_dir:
        WORKING_DIR = pathlib.Path(cli_args.working_dir).resolve()
    else:
        WORKING_DIR = MAKEFILE_PATH.parent.resolve() if MAKEFILE_PATH.exists() else pathlib.Path.cwd()

# Parse include/exclude lists
INCLUDE_TARGETS: Optional[Set[str]] = None
if cli_args.include:
    INCLUDE_TARGETS = set(target.strip() for target in cli_args.include.split(","))

EXCLUDE_TARGETS: Set[str] = set()
if cli_args.exclude:
    EXCLUDE_TARGETS = set(target.strip() for target in cli_args.exclude.split(","))

# MCP Server instance
mcp_server = FastMCP("MakefileMCP")


class MakefileParser:
    """Parser for extracting targets and descriptions from Makefiles."""

    def __init__(self, makefile_path: pathlib.Path):
        self.makefile_path = makefile_path
        self.targets: Dict[str, str] = {}
        self._parse()

    def _parse(self):
        """Parse the Makefile to extract targets and their descriptions."""
        try:
            with open(self.makefile_path, "r", encoding="utf-8") as f:
                content = f.read()
        except UnicodeDecodeError:
            with open(self.makefile_path, "r", encoding="latin-1") as f:
                content = f.read()

        lines = content.split("\n")
        current_comment = ""

        for _i, line in enumerate(lines):
            line = line.rstrip()

            # Track comments that might describe the next target
            if line.startswith("#"):
                comment = line[1:].strip()
                if comment and not comment.startswith("#"):  # Skip comment headers like "###"
                    current_comment = comment
                continue

            # Skip empty lines but reset comment
            if not line.strip():
                current_comment = ""
                continue

            # Look for target definitions (target: dependencies)
            target_match = re.match(r"^([a-zA-Z0-9_.-]+)\s*:", line)
            if target_match:
                target_name = target_match.group(1)

                # Skip special targets that start with . or contain %
                if target_name.startswith(".") or "%" in target_name:
                    current_comment = ""
                    continue

                # Use the comment as description, or generate a default one
                if current_comment:
                    description = current_comment
                else:
                    description = f"Execute the '{target_name}' target"

                self.targets[target_name] = description
                current_comment = ""
                continue

            # If line doesn't start with tab/space, reset comment
            if line and not line.startswith(("\t", " ")):
                current_comment = ""

    def get_targets(self) -> Dict[str, str]:
        """Get all discovered targets with their descriptions."""
        return self.targets.copy()

    def get_filtered_targets(self, include: Optional[Set[str]], exclude: Set[str]) -> Dict[str, str]:
        """Get targets filtered by include/exclude lists."""
        targets = self.get_targets()

        # Apply include filter
        if include is not None:
            targets = {name: desc for name, desc in targets.items() if name in include}

        # Apply exclude filter
        if exclude:
            targets = {name: desc for name, desc in targets.items() if name not in exclude}

        return targets


def get_makefile_targets():
    """Parse the Makefile and return filtered targets."""
    if not MAKEFILE_PATH or not MAKEFILE_PATH.exists():
        return {}

    parser = MakefileParser(MAKEFILE_PATH)
    filtered_targets = parser.get_filtered_targets(INCLUDE_TARGETS, EXCLUDE_TARGETS)

    if not filtered_targets:
        print("Warning: No targets found or all targets filtered out", file=sys.stderr)

    return filtered_targets


# Initialize targets only when running as script
if __name__ == "__main__":
    filtered_targets = get_makefile_targets()
else:
    # For imports, initialize as empty dict
    filtered_targets = {}


def create_make_tool(target_name: str, description: str):
    """Create an MCP tool for a specific make target."""

    def make_target(
        additional_args: Optional[str] = None, dry_run: bool = False, max_output_tokens: Optional[int] = None
    ) -> Dict[str, Any]:
        """Execute the make target with optional arguments and dry-run capability."""
        try:
            # Build the make command
            cmd = ["make", "-C", str(WORKING_DIR), target_name]

            if dry_run:
                cmd.append("-n")  # Dry run flag for make

            if additional_args:
                # Split additional args and add them
                cmd.extend(additional_args.split())

            # Execute the command - safe execution with list of args, no shell injection risk
            result = subprocess.run(  # noqa: S603
                cmd,
                capture_output=True,
                text=True,
                timeout=300,  # 5 minute timeout
            )

            # Determine token limit
            token_limit = max_output_tokens if max_output_tokens is not None else cli_args.max_output_tokens

            # Function to truncate text to approximate token limit
            def truncate_to_tokens(text: str, max_tokens: int) -> tuple[str, bool]:
                """Truncate text to approximately max_tokens. Returns (text, was_truncated)."""
                if not text:
                    return text, False

                # Rough approximation: 4 characters per token on average
                max_chars = max_tokens * 4
                if len(text) <= max_chars:
                    return text, False

                # Truncate and add a note
                truncated_text = text[:max_chars]
                # Try to break at a line boundary near the end
                last_newline = truncated_text.rfind("\n", max(0, max_chars - 100))
                if last_newline > max_chars // 2:  # Only use line break if it's not too early
                    truncated_text = truncated_text[:last_newline]

                return truncated_text, True

            # Truncate output if needed
            stdout, stdout_truncated = truncate_to_tokens(result.stdout, token_limit)
            stderr, stderr_truncated = truncate_to_tokens(result.stderr, token_limit)

            response = {
                "target": target_name,
                "command": " ".join(cmd),
                "working_directory": str(WORKING_DIR),
                "exit_code": result.returncode,
                "stdout": stdout,
                "stderr": stderr,
            }

            # Add truncation notes if applicable
            if stdout_truncated:
                response["stdout_truncated"] = True
                response["stdout_truncation_note"] = (
                    f"Output truncated to ~{token_limit} tokens. Use max_output_tokens parameter to adjust limit."
                )

            if stderr_truncated:
                response["stderr_truncated"] = True
                response["stderr_truncation_note"] = (
                    f"Error output truncated to ~{token_limit} tokens. Use max_output_tokens parameter to adjust limit."
                )

            if dry_run:
                response["note"] = "This was a dry run - no commands were actually executed"

            if result.returncode == 0:
                response["status"] = "success"
                response["message"] = f"Successfully executed target '{target_name}'"
            else:
                response["status"] = "error"
                response["message"] = f"Target '{target_name}' failed with exit code {result.returncode}"

            return response

        except subprocess.TimeoutExpired:
            return {
                "target": target_name,
                "status": "error",
                "message": f"Target '{target_name}' timed out after 5 minutes",
                "exit_code": -1,
            }
        except subprocess.SubprocessError as e:
            return {
                "target": target_name,
                "status": "error",
                "message": f"Failed to execute target '{target_name}': {str(e)}",
                "exit_code": -1,
            }
        except Exception as e:
            return {
                "target": target_name,
                "status": "error",
                "message": f"Unexpected error executing target '{target_name}': {str(e)}",
                "exit_code": -1,
            }

    # Set the function name and docstring dynamically
    tool_name = f"make_{target_name.replace('-', '_').replace('.', '_')}"
    make_target.__name__ = tool_name
    make_target.__doc__ = f"{description}.\n\nExecutes: make -C {WORKING_DIR} {target_name}"

    # Register the tool with the MCP server
    mcp_server.tool()(make_target)

    return make_target


# Create tools for each filtered target
created_tools = []
for target_name, description in filtered_targets.items():
    tool_func = create_make_tool(target_name, description)
    created_tools.append((target_name, tool_func))


@mcp_server.tool()
def list_available_targets() -> Dict[str, Any]:
    """
    List all available make targets that can be executed through this server.

    Returns:
        dict: Information about available targets and server configuration.
    """
    return {
        "makefile_path": str(MAKEFILE_PATH),
        "working_directory": str(WORKING_DIR),
        "total_targets_in_makefile": (
            len(MakefileParser(MAKEFILE_PATH).get_targets()) if MAKEFILE_PATH and MAKEFILE_PATH.exists() else 0
        ),
        "available_targets": len(filtered_targets),
        "targets": [
            {"name": name, "description": desc, "tool_name": f"make_{name.replace('-', '_').replace('.', '_')}"}
            for name, desc in filtered_targets.items()
        ],
        "include_filter": list(INCLUDE_TARGETS) if INCLUDE_TARGETS else None,
        "exclude_filter": list(EXCLUDE_TARGETS) if EXCLUDE_TARGETS else None,
    }


@mcp_server.tool()
def get_makefile_info() -> Dict[str, Any]:
    """
    Get detailed information about the Makefile and its targets.

    Returns:
        dict: Comprehensive information about the Makefile.
    """
    all_targets = MakefileParser(MAKEFILE_PATH).get_targets() if MAKEFILE_PATH and MAKEFILE_PATH.exists() else {}

    return {
        "makefile_path": str(MAKEFILE_PATH),
        "makefile_exists": MAKEFILE_PATH.exists(),
        "working_directory": str(WORKING_DIR),
        "all_targets": {
            "count": len(all_targets),
            "targets": [{"name": name, "description": desc} for name, desc in all_targets.items()],
        },
        "filtered_targets": {
            "count": len(filtered_targets),
            "targets": [{"name": name, "description": desc} for name, desc in filtered_targets.items()],
        },
        "filters": {
            "include": list(INCLUDE_TARGETS) if INCLUDE_TARGETS else None,
            "exclude": list(EXCLUDE_TARGETS) if EXCLUDE_TARGETS else None,
        },
    }


if __name__ == "__main__":
    if not filtered_targets:
        print("Error: No make targets available to expose as tools", file=sys.stderr)
        sys.exit(1)

    print("Starting Makefile MCP server")
    print(f"  Makefile: {MAKEFILE_PATH}")
    print(f"  Working directory: {WORKING_DIR}")
    print(f"  Available targets: {', '.join(filtered_targets.keys())}")

    if INCLUDE_TARGETS:
        print(f"  Include filter: {', '.join(INCLUDE_TARGETS)}")
    if EXCLUDE_TARGETS:
        print(f"  Exclude filter: {', '.join(EXCLUDE_TARGETS)}")

    mcp_server.run()
