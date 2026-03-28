"""Tests for the MCP server tool registration."""
from __future__ import annotations

import asyncio
import pytest
from antientropy_mcp.server import mcp

EXPECTED_TOOLS = {
    "antientropy_glob",
    "antientropy_grep",
    "antientropy_read",
    "antientropy_categories",
    "antientropy_sync",
}


def test_all_tools_registered():
    """All 5 tools should be registered on the FastMCP instance."""
    tools = asyncio.run(mcp.list_tools())
    registered_names = {t.name for t in tools}
    assert EXPECTED_TOOLS == registered_names, (
        f"Expected tools {EXPECTED_TOOLS}, got {registered_names}"
    )


@pytest.mark.parametrize("tool_name", sorted(EXPECTED_TOOLS))
def test_individual_tool_present(tool_name: str):
    """Each individual tool should be present in the registry."""
    tools = asyncio.run(mcp.list_tools())
    names = {t.name for t in tools}
    assert tool_name in names
