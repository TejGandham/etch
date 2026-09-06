"""Tests for the MCP server surface.

The plugin launches via ``uvx --from <plugin-root> etch``, which resolves
dependencies fresh on every install. These tests pin down that the module
imports and registers its tools against whatever ``mcp`` release the
pyproject constraint resolves to, and that the constraint can never drift
onto a new major (mcp 2.0 removed ``mcp.server.fastmcp``).
"""

import asyncio
import re
import tomllib
from pathlib import Path

import etch

EXPECTED_TOOLS = {"start_diagram_job", "start_variant_job", "check_job_status"}
PYPROJECT = Path(__file__).resolve().parent.parent / "pyproject.toml"


def test_server_registers_expected_tools():
    tools = asyncio.run(etch.mcp.list_tools())
    assert {tool.name for tool in tools} == EXPECTED_TOOLS


def test_pyproject_bounds_mcp_major_version():
    """An unbounded ``mcp>=x`` let a fresh uvx resolve pick up mcp 2.x and break import."""
    dependencies = tomllib.loads(PYPROJECT.read_text())["project"]["dependencies"]
    mcp_spec = next(dep for dep in dependencies if re.match(r"^mcp\s*[><=!~\[]", dep))
    assert "<" in mcp_spec, f"mcp dependency needs an upper bound, got {mcp_spec!r}"
