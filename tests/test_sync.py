"""Tests for antientropy_mcp.sync (pure functions only — no real API calls)."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import httpx
import pytest
import pytest_asyncio

from antientropy_mcp.sync import (
    extract_article_data,
    extract_category_tree,
    fetch_article,
    parse_sitemap,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

SITEMAP_XML = """\
<?xml version="1.0" encoding="UTF-8"?>
<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
  <url>
    <loc>https://resourceportal.antientropy.org/docs/getting-started</loc>
    <lastmod>2024-03-01</lastmod>
  </url>
  <url>
    <loc>https://resourceportal.antientropy.org/docs/advanced-usage</loc>
    <lastmod>2024-03-15</lastmod>
  </url>
  <url>
    <loc>https://resourceportal.antientropy.org/about</loc>
    <lastmod>2024-02-01</lastmod>
  </url>
</urlset>
"""

MOCK_API_RESPONSE = {
    "result": {
        "articleData": {
            "id": "article-uuid-123",
            "title": "Getting Started",
            "categoryId": "cat-child-uuid",
            "articleContentForSsr": "<p>Hello world</p>",
            "settings": {"slug": "getting-started"},
        },
        "categories": {
            "id": "root",
            "title": "Root",
            "categoryType": 1,
            "children": [
                {
                    "id": "cat-parent-uuid",
                    "title": "Parent Category",
                    "categoryType": 1,
                    "children": [
                        {
                            "id": "cat-child-uuid",
                            "title": "Child Category",
                            "categoryType": 1,
                            "children": [],
                        }
                    ],
                }
            ],
        },
    }
}


# ---------------------------------------------------------------------------
# parse_sitemap
# ---------------------------------------------------------------------------


def test_parse_sitemap_returns_docs_entries():
    entries = parse_sitemap(SITEMAP_XML)
    assert len(entries) == 2
    slugs = [e["slug"] for e in entries]
    assert "getting-started" in slugs
    assert "advanced-usage" in slugs


def test_parse_sitemap_filters_non_docs():
    entries = parse_sitemap(SITEMAP_XML)
    urls = [e["url"] for e in entries]
    assert all("/docs/" in url for url in urls)
    assert "https://resourceportal.antientropy.org/about" not in urls


def test_parse_sitemap_entry_shape():
    entries = parse_sitemap(SITEMAP_XML)
    entry = next(e for e in entries if e["slug"] == "getting-started")
    assert entry["url"] == "https://resourceportal.antientropy.org/docs/getting-started"
    assert entry["lastmod"] == "2024-03-01"
    assert entry["slug"] == "getting-started"


def test_parse_sitemap_missing_lastmod():
    xml = """\
<?xml version="1.0" encoding="UTF-8"?>
<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
  <url>
    <loc>https://resourceportal.antientropy.org/docs/no-date</loc>
  </url>
</urlset>
"""
    entries = parse_sitemap(xml)
    assert len(entries) == 1
    assert entries[0]["lastmod"] == ""


# ---------------------------------------------------------------------------
# extract_category_tree
# ---------------------------------------------------------------------------


def test_extract_category_tree_returns_categories():
    tree = extract_category_tree(MOCK_API_RESPONSE)
    assert tree == MOCK_API_RESPONSE["result"]["categories"]
    assert "children" in tree


# ---------------------------------------------------------------------------
# extract_article_data
# ---------------------------------------------------------------------------


def test_extract_article_data_basic_fields():
    data = extract_article_data(MOCK_API_RESPONSE, MOCK_API_RESPONSE["result"]["categories"])
    assert data["title"] == "Getting Started"
    assert data["id"] == "article-uuid-123"
    assert "<p>Hello world</p>" in data["html"]


def test_extract_article_data_category_path():
    data = extract_article_data(MOCK_API_RESPONSE, MOCK_API_RESPONSE["result"]["categories"])
    assert data["category_path"] == "Parent Category/Child Category"


def test_extract_article_data_nested_category_path():
    """Category path resolves through multiple nesting levels."""
    api_response = {
        "result": {
            "articleData": {
                "id": "art-uuid",
                "title": "Deep Article",
                "categoryId": "level3-uuid",
                "articleContentForSsr": "",
                "settings": {"slug": "deep-article"},
            },
            "categories": {
                "id": "root",
                "title": "Root",
                "categoryType": 1,
                "children": [
                    {
                        "id": "level1-uuid",
                        "title": "Level 1",
                        "categoryType": 1,
                        "children": [
                            {
                                "id": "level2-uuid",
                                "title": "Level 2",
                                "categoryType": 1,
                                "children": [
                                    {
                                        "id": "level3-uuid",
                                        "title": "Level 3",
                                        "categoryType": 1,
                                        "children": [],
                                    }
                                ],
                            }
                        ],
                    }
                ],
            },
        }
    }
    data = extract_article_data(api_response, api_response["result"]["categories"])
    assert data["category_path"] == "Level 1/Level 2/Level 3"


def test_extract_article_data_unknown_category():
    """Falls back gracefully when categoryId is not in the tree."""
    response = {
        "result": {
            "articleData": {
                "id": "art-uuid",
                "title": "Orphan Article",
                "categoryId": "nonexistent-uuid",
                "articleContentForSsr": "<p>content</p>",
                "settings": {"slug": "orphan"},
            },
            "categories": {
                "id": "root",
                "title": "Root",
                "categoryType": 1,
                "children": [],
            },
        }
    }
    data = extract_article_data(response, response["result"]["categories"])
    assert data["category_path"] == ""


# ---------------------------------------------------------------------------
# fetch_article
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_fetch_article_success():
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {"result": {"articleData": {"title": "Test"}}}
    mock_response.raise_for_status = MagicMock()

    mock_client = AsyncMock(spec=httpx.AsyncClient)
    mock_client.get = AsyncMock(return_value=mock_response)

    result = await fetch_article(mock_client, "test-slug")

    assert result == {"result": {"articleData": {"title": "Test"}}}
    mock_client.get.assert_awaited_once()
    call_url = mock_client.get.call_args[0][0]
    assert "test-slug" in call_url


@pytest.mark.asyncio
async def test_fetch_article_404_returns_none():
    mock_response = MagicMock()
    mock_response.status_code = 404
    mock_response.raise_for_status = MagicMock(
        side_effect=httpx.HTTPStatusError(
            "Not found",
            request=MagicMock(),
            response=mock_response,
        )
    )

    mock_client = AsyncMock(spec=httpx.AsyncClient)
    mock_client.get = AsyncMock(return_value=mock_response)

    result = await fetch_article(mock_client, "missing-slug")
    assert result is None


@pytest.mark.asyncio
async def test_fetch_article_network_error_returns_none():
    mock_client = AsyncMock(spec=httpx.AsyncClient)
    mock_client.get = AsyncMock(side_effect=httpx.RequestError("connection error", request=MagicMock()))

    result = await fetch_article(mock_client, "some-slug")
    assert result is None
