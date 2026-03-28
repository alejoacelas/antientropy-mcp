from __future__ import annotations

import os
from pathlib import Path

from mcp.server.fastmcp import FastMCP
from starlette.requests import Request
from starlette.responses import JSONResponse, Response
from starlette.types import ASGIApp, Receive, Scope, Send

from antientropy_mcp.cache import ArticleCache
from antientropy_mcp.sync import sync as run_sync

# ---------------------------------------------------------------------------
# Configuration from environment
# ---------------------------------------------------------------------------

CACHE_DIR = Path(os.environ.get("CACHE_DIR", str(Path.home() / ".antientropy-mcp")))
AUTH_TOKEN = os.environ.get("AUTH_TOKEN")

cache = ArticleCache(CACHE_DIR)

mcp = FastMCP(
    name="antientropy",
    instructions=(
        "Search and read articles from the AntiEntropy Resource Portal "
        "(https://resourceportal.antientropy.org/docs). "
        "Use antientropy_glob to find articles, antientropy_grep to search content, "
        "and antientropy_read to read full articles. "
        "Run antientropy_sync on first use to populate the cache."
    ),
)


# ---------------------------------------------------------------------------
# Auth middleware (used when running over HTTP with AUTH_TOKEN set)
# ---------------------------------------------------------------------------


class BearerAuthMiddleware:
    """ASGI middleware that rejects /mcp requests without a valid Bearer token."""

    def __init__(self, app: ASGIApp, token: str) -> None:
        self.app = app
        self.token = token

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] == "http":
            path = scope.get("path", "")
            if path.startswith("/mcp"):
                headers = dict(scope.get("headers", []))
                auth = headers.get(b"authorization", b"").decode()
                if auth != f"Bearer {self.token}":
                    response = JSONResponse(
                        {"error": "Unauthorized"}, status_code=401
                    )
                    await response(scope, receive, send)
                    return
        await self.app(scope, receive, send)


# ---------------------------------------------------------------------------
# Tools
# ---------------------------------------------------------------------------


@mcp.tool()
def antientropy_glob(pattern: str = "**") -> str:
    """Find articles matching a glob pattern.

    Pattern matches against the virtual path: {category_path}/{slug}
    Examples: '**/*gdpr*', '*policy*', 'Governance*/**', '**' (all)
    Returns matching articles with titles and category paths.
    """
    return cache.glob_articles(pattern)

@mcp.tool()
def antientropy_grep(
    pattern: str,
    case_insensitive: bool = False,
    context_lines: int = 0,
    head_limit: int = 50,
) -> str:
    """Search article content with a regex pattern.

    Returns matches formatted like ripgrep: slug:line_number:matching_line
    """
    return cache.grep_articles(
        pattern,
        case_insensitive=case_insensitive,
        context_lines=context_lines,
        head_limit=head_limit,
    )

@mcp.tool()
def antientropy_read(
    article_slug: str,
    offset: int = 0,
    limit: int = 2000,
) -> str:
    """Read an article's content by slug.

    Returns content with line numbers (cat -n format).
    Use antientropy_glob or antientropy_grep to discover slugs.
    """
    return cache.read_article(article_slug, offset=offset, limit=limit)

@mcp.tool()
def antientropy_categories() -> str:
    """List the category tree of the AntiEntropy Resource Portal."""
    return cache.format_category_tree()

@mcp.tool()
async def antientropy_sync(force: bool = False) -> str:
    """Sync the local article cache with the remote portal.

    Run on first use to populate the cache, or anytime to pull updates.
    Set force=True to re-fetch all articles regardless of lastmod.
    """
    return await run_sync(cache, force=force)


# ---------------------------------------------------------------------------
# Health check
# ---------------------------------------------------------------------------


@mcp.custom_route("/healthz", methods=["GET"])
async def health_check(request: Request) -> Response:
    return JSONResponse({"status": "ok"})


if __name__ == "__main__":
    mcp.run(transport="stdio")
