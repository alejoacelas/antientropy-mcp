"""Sync pipeline: sitemap parsing, API fetching, and cache writing."""

from __future__ import annotations

import argparse
import asyncio
import xml.etree.ElementTree as ET
from typing import Any

import httpx

from antientropy_mcp.cache import ArticleCache
from antientropy_mcp.converter import convert_article_html


_SITEMAP_URL = "https://resourceportal.antientropy.org/sitemap-en.xml"
_ARTICLE_API_URL = (
    "https://resourceportal.antientropy.org/api/document/get-article-body"
    "?article-slug={slug}"
)
_REQUEST_DELAY = 0.5  # seconds between API requests

_SITEMAP_NS = "http://www.sitemaps.org/schemas/sitemap/0.9"


# ---------------------------------------------------------------------------
# Sitemap parsing
# ---------------------------------------------------------------------------


def parse_sitemap(xml_text: str) -> list[dict]:
    """Parse sitemap XML and return entries that contain '/docs/' in the URL.

    Each entry is a dict with keys: slug, lastmod, url.
    """
    root = ET.fromstring(xml_text)

    entries: list[dict] = []
    for url_el in root.findall(f"{{{_SITEMAP_NS}}}url"):
        loc_el = url_el.find(f"{{{_SITEMAP_NS}}}loc")
        if loc_el is None or loc_el.text is None:
            continue
        loc = loc_el.text.strip()

        if "/docs/" not in loc:
            continue

        lastmod_el = url_el.find(f"{{{_SITEMAP_NS}}}lastmod")
        lastmod = (lastmod_el.text or "").strip() if lastmod_el is not None else ""

        # Extract slug: everything after /docs/
        slug = loc.split("/docs/", 1)[1]

        entries.append({"slug": slug, "lastmod": lastmod, "url": loc})

    return entries


# ---------------------------------------------------------------------------
# API fetching
# ---------------------------------------------------------------------------


async def fetch_article(client: httpx.AsyncClient, slug: str) -> dict | None:
    """Fetch article JSON from the Document360 API.

    Returns parsed JSON dict, or None on any error.
    """
    url = _ARTICLE_API_URL.format(slug=slug)
    try:
        response = await client.get(url)
        response.raise_for_status()
        return response.json()
    except (httpx.HTTPStatusError, httpx.RequestError):
        return None


# ---------------------------------------------------------------------------
# Data extraction
# ---------------------------------------------------------------------------


def _find_category_path(tree: dict, target_id: str, ancestors: list[str]) -> list[str] | None:
    """Recursively walk the category tree and return the path to target_id.

    Returns a list of titles from the tree root's children down to (and
    including) the matching node, or None if not found.
    """
    node_id = tree.get("id", "")
    node_title = tree.get("title", "")

    current_path = ancestors + ([node_title] if node_title else [])

    if node_id == target_id:
        return current_path

    for child in tree.get("children", []):
        result = _find_category_path(child, target_id, current_path)
        if result is not None:
            return result

    return None


def extract_category_tree(api_response: dict) -> dict:
    """Return the categories subtree from an API response."""
    return api_response["result"]["categories"]


def extract_article_data(api_response: dict, category_tree: dict) -> dict:
    """Extract relevant fields from an API response.

    Returns a dict with: title, html, id, category_path.
    """
    article_data: dict[str, Any] = api_response["result"]["articleData"]
    title: str = article_data.get("title", "")
    html: str = article_data.get("articleContentForSsr", "") or ""
    article_id: str = article_data.get("id", "")
    category_id: str = article_data.get("categoryId", "")

    # Walk the tree. The root node itself is not included in the path — we
    # start building the path from its children.
    path_nodes: list[str] | None = None
    for child in category_tree.get("children", []):
        path_nodes = _find_category_path(child, category_id, [])
        if path_nodes is not None:
            break

    category_path = "/".join(path_nodes) if path_nodes else ""

    return {
        "title": title,
        "html": html,
        "id": article_id,
        "category_path": category_path,
    }


# ---------------------------------------------------------------------------
# Main sync orchestrator
# ---------------------------------------------------------------------------


async def sync(cache: ArticleCache, force: bool = False) -> str:
    """Fetch changed articles from the API and write them to the cache.

    Returns a human-readable summary string.
    """
    async with httpx.AsyncClient(timeout=30) as client:
        # 1. Fetch sitemap
        sitemap_response = await client.get(_SITEMAP_URL)
        sitemap_response.raise_for_status()
        sitemap_entries = parse_sitemap(sitemap_response.text)

        total_in_sitemap = len(sitemap_entries)

        # 2. Load existing index to diff
        existing_index = cache.load_index() if not force else {}

        # 3. Determine which articles need updating
        to_fetch: list[dict] = []
        for entry in sitemap_entries:
            slug = entry["slug"]
            lastmod = entry["lastmod"]
            existing = existing_index.get(slug)
            if existing is None or existing.get("lastmod") != lastmod:
                to_fetch.append(entry)

        # 4. Fetch and write changed articles
        fetched_count = 0
        category_tree: dict | None = None

        for i, entry in enumerate(to_fetch):
            if i > 0:
                await asyncio.sleep(_REQUEST_DELAY)

            slug = entry["slug"]
            url = entry["url"]
            lastmod = entry["lastmod"]

            api_response = await fetch_article(client, slug)
            if api_response is None:
                continue

            # Save category tree from the first successful response
            if category_tree is None:
                category_tree = extract_category_tree(api_response)
                cache.save_categories(category_tree)

            data = extract_article_data(api_response, category_tree)
            markdown = convert_article_html(data["html"])

            cache.write_article(
                slug=slug,
                title=data["title"],
                category_path=data["category_path"],
                content=markdown,
                lastmod=lastmod,
                article_id=data["id"],
                url=url,
            )
            fetched_count += 1

        # 5. Persist index
        cache.save_index()

        return (
            f"Synced {fetched_count}/{len(to_fetch)} articles "
            f"({total_in_sitemap} total in sitemap)"
        )


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------


def cli_sync() -> None:
    """Synchronous CLI entry point for cron jobs."""
    parser = argparse.ArgumentParser(description="Sync antientropy article cache")
    parser.add_argument(
        "--force",
        action="store_true",
        help="Re-fetch all articles regardless of lastmod",
    )
    parser.add_argument(
        "--cache-dir",
        default=".cache",
        help="Directory for article cache (default: .cache)",
    )
    args = parser.parse_args()

    cache = ArticleCache(args.cache_dir)
    summary = asyncio.run(sync(cache, force=args.force))
    print(summary)
