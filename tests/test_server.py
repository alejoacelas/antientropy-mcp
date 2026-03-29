"""Tests for the MCP server tool registration."""
from __future__ import annotations

import asyncio
import os
from unittest.mock import patch

import pytest

from antientropy_mcp.server import mcp

EXPECTED_TOOLS = {
    "antientropy_glob",
    "antientropy_grep",
    "antientropy_read",
    "antientropy_categories",
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


def test_default_cache_dir():
    """Without CACHE_DIR env var, uses ~/.antientropy-mcp."""
    from pathlib import Path
    with patch.dict(os.environ, {}, clear=False):
        os.environ.pop("CACHE_DIR", None)
        import importlib
        import antientropy_mcp.server as srv
        importlib.reload(srv)
        assert srv.CACHE_DIR == Path.home() / ".antientropy-mcp"


def test_custom_cache_dir(tmp_path):
    """CACHE_DIR env var overrides the default."""
    with patch.dict(os.environ, {"CACHE_DIR": str(tmp_path)}):
        import importlib
        import antientropy_mcp.server as srv
        importlib.reload(srv)
        assert srv.CACHE_DIR == tmp_path


def test_auth_token_not_required_by_default():
    """Without AUTH_TOKEN env var, no auth is needed."""
    with patch.dict(os.environ, {}, clear=False):
        os.environ.pop("AUTH_TOKEN", None)
        import importlib
        import antientropy_mcp.server as srv
        importlib.reload(srv)
        assert srv.AUTH_TOKEN is None


def test_auth_token_read_from_env():
    """AUTH_TOKEN env var is picked up."""
    with patch.dict(os.environ, {"AUTH_TOKEN": "secret123"}):
        import importlib
        import antientropy_mcp.server as srv
        importlib.reload(srv)
        assert srv.AUTH_TOKEN == "secret123"


def test_health_check_registered():
    """Health check function should exist and be callable."""
    from antientropy_mcp.server import health_check
    assert callable(health_check)


def test_bearer_auth_middleware_exists():
    """BearerAuthMiddleware should be importable."""
    from antientropy_mcp.server import BearerAuthMiddleware
    assert BearerAuthMiddleware is not None
