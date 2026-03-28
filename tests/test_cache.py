"""Tests for the ArticleCache class."""

import json
from pathlib import Path

import pytest

from antientropy_mcp.cache import ArticleCache


def test_cache_init_creates_dirs(tmp_path):
    cache = ArticleCache(tmp_path)
    assert (tmp_path / "articles").is_dir()


def test_write_and_read_article(tmp_path):
    cache = ArticleCache(tmp_path)
    cache.write_article(
        slug="test-article",
        title="Test Article",
        category_path="Category/Subcategory",
        content="# Hello\n\nThis is a test.",
        lastmod="2024-01-01T00:00:00Z",
        article_id="abc-123",
        url="https://example.com/docs/test-article",
    )
    result = cache.read_article("test-article")
    assert "Test Article" in result  # title shown in header
    assert "# Hello" in result
    assert "This is a test." in result


def test_read_article_with_line_numbers(tmp_path):
    cache = ArticleCache(tmp_path)
    cache.write_article(
        slug="test-article",
        title="Test",
        category_path="Cat",
        content="Line one\nLine two\nLine three",
        lastmod="2024-01-01T00:00:00Z",
        article_id="abc",
        url="https://example.com/docs/test",
    )
    result = cache.read_article("test-article")
    assert "\t" in result  # tab-separated line numbers


def test_read_article_with_offset_limit(tmp_path):
    cache = ArticleCache(tmp_path)
    lines = "\n".join(f"Line {i}" for i in range(1, 51))
    cache.write_article(
        slug="long",
        title="Long",
        category_path="Cat",
        content=lines,
        lastmod="2024-01-01T00:00:00Z",
        article_id="abc",
        url="https://example.com/docs/long",
    )
    result = cache.read_article("long", offset=10, limit=5)
    assert "Line 11" in result
    assert "Line 15" in result
    assert "Line 16" not in result


def test_glob_all(tmp_path):
    cache = ArticleCache(tmp_path)
    for i in range(3):
        cache.write_article(
            slug=f"article-{i}",
            title=f"Article {i}",
            category_path="Category",
            content=f"Content {i}",
            lastmod="2024-01-01T00:00:00Z",
            article_id=f"id-{i}",
            url=f"https://example.com/docs/article-{i}",
        )
    cache.save_index()
    results = cache.glob_articles("**")
    # glob returns a formatted string; count articles by lines that contain slugs
    assert "article-0" in results
    assert "article-1" in results
    assert "article-2" in results


def test_glob_pattern_matching(tmp_path):
    cache = ArticleCache(tmp_path)
    cache.write_article(
        slug="gdpr-guide",
        title="GDPR Guide",
        category_path="Governance/GDPR",
        content="...",
        lastmod="2024-01-01T00:00:00Z",
        article_id="1",
        url="u",
    )
    cache.write_article(
        slug="travel-policy",
        title="Travel Policy",
        category_path="Policies/Travel",
        content="...",
        lastmod="2024-01-01T00:00:00Z",
        article_id="2",
        url="u",
    )
    cache.save_index()
    results = cache.glob_articles("*gdpr*")
    assert "gdpr-guide" in results
    assert "travel-policy" not in results


def test_grep_content(tmp_path):
    cache = ArticleCache(tmp_path)
    cache.write_article(
        slug="art1",
        title="Art 1",
        category_path="Cat",
        content="The quick brown fox\njumped over the lazy dog",
        lastmod="2024-01-01T00:00:00Z",
        article_id="1",
        url="u",
    )
    cache.write_article(
        slug="art2",
        title="Art 2",
        category_path="Cat",
        content="No match here\nNothing relevant",
        lastmod="2024-01-01T00:00:00Z",
        article_id="2",
        url="u",
    )
    cache.save_index()
    results = cache.grep_articles("quick.*fox")
    assert "art1" in results
    assert "art2" not in results


def test_read_nonexistent_article(tmp_path):
    cache = ArticleCache(tmp_path)
    result = cache.read_article("nonexistent")
    assert "not found" in result.lower() or "error" in result.lower()


# ---------------------------------------------------------------------------
# Additional tests
# ---------------------------------------------------------------------------


def test_write_article_creates_file(tmp_path):
    cache = ArticleCache(tmp_path)
    cache.write_article(
        slug="my-slug",
        title="My Title",
        category_path="A/B",
        content="body text",
        lastmod="2024-06-01T00:00:00Z",
        article_id="uuid-xyz",
        url="https://example.com/docs/my-slug",
    )
    article_file = tmp_path / "articles" / "my-slug.md"
    assert article_file.exists()
    raw = article_file.read_text()
    assert 'title: "My Title"' in raw
    assert "slug: my-slug" in raw
    assert "id: uuid-xyz" in raw
    assert 'category_path: "A/B"' in raw
    assert "body text" in raw


def test_save_and_load_index(tmp_path):
    cache = ArticleCache(tmp_path)
    cache.write_article(
        slug="s1",
        title="T1",
        category_path="X",
        content="c",
        lastmod="2024-01-01T00:00:00Z",
        article_id="i1",
        url="u1",
    )
    cache.save_index()
    index_file = tmp_path / "_index.json"
    assert index_file.exists()

    cache2 = ArticleCache(tmp_path)
    loaded = cache2.load_index()
    assert "s1" in loaded
    assert loaded["s1"]["title"] == "T1"
    assert loaded["s1"]["category_path"] == "X"
    assert loaded["s1"]["id"] == "i1"
    assert loaded["s1"]["url"] == "u1"


def test_load_index_empty_if_no_file(tmp_path):
    cache = ArticleCache(tmp_path)
    result = cache.load_index()
    assert result == {}


def test_save_and_load_categories(tmp_path):
    cache = ArticleCache(tmp_path)
    tree = {"name": "Root", "children": [{"name": "Child", "article_count": 2}]}
    cache.save_categories(tree)
    loaded = cache.load_categories()
    assert loaded["name"] == "Root"
    assert loaded["children"][0]["article_count"] == 2


def test_format_category_tree_no_data(tmp_path):
    cache = ArticleCache(tmp_path)
    result = cache.format_category_tree()
    assert "no categories" in result.lower()


def test_format_category_tree_with_data(tmp_path):
    cache = ArticleCache(tmp_path)
    tree = {
        "children": [
            {
                "title": "Policies",
                "categoryType": 1,
                "children": [
                    {"title": "Travel Policy", "slug": "travel", "categoryType": 0, "children": []},
                    {"title": "Expense Policy", "slug": "expense", "categoryType": 0, "children": []},
                ],
            },
            {
                "title": "Governance",
                "categoryType": 2,
                "children": [
                    {"title": "Board", "slug": "board", "categoryType": 0, "children": []},
                ],
            },
        ],
    }
    cache.save_categories(tree)
    result = cache.format_category_tree()
    assert "Policies" in result
    assert "Governance" in result
    assert "2 articles" in result  # Policies has 2 articles
    assert "Travel Policy" in result


def test_grep_case_insensitive(tmp_path):
    cache = ArticleCache(tmp_path)
    cache.write_article(
        slug="art1",
        title="Art 1",
        category_path="Cat",
        content="Hello World\nnothing here",
        lastmod="2024-01-01T00:00:00Z",
        article_id="1",
        url="u",
    )
    cache.save_index()
    result_sensitive = cache.grep_articles("hello world", case_insensitive=False)
    assert "art1" not in result_sensitive

    result_insensitive = cache.grep_articles("hello world", case_insensitive=True)
    assert "art1" in result_insensitive


def test_grep_context_lines(tmp_path):
    cache = ArticleCache(tmp_path)
    cache.write_article(
        slug="ctx",
        title="Ctx",
        category_path="Cat",
        content="before\nmatch line\nafter",
        lastmod="2024-01-01T00:00:00Z",
        article_id="1",
        url="u",
    )
    cache.save_index()
    result = cache.grep_articles("match line", context_lines=1)
    assert "before" in result
    assert "after" in result


def test_glob_matches_title(tmp_path):
    """Glob should also match against title, not only category_path/slug."""
    cache = ArticleCache(tmp_path)
    cache.write_article(
        slug="policy-doc",
        title="Travel Reimbursement Policy",
        category_path="Finance",
        content="content",
        lastmod="2024-01-01T00:00:00Z",
        article_id="1",
        url="u",
    )
    cache.save_index()
    results = cache.glob_articles("*Travel*")
    assert "policy-doc" in results


def test_glob_matches_category(tmp_path):
    """Glob should match against category path."""
    cache = ArticleCache(tmp_path)
    cache.write_article(
        slug="some-doc",
        title="Some Document",
        category_path="Human Resources/Benefits",
        content="content",
        lastmod="2024-01-01T00:00:00Z",
        article_id="1",
        url="u",
    )
    cache.save_index()
    results = cache.glob_articles("*Benefits*")
    assert "some-doc" in results


def test_in_memory_index_updated_on_write(tmp_path):
    """Index dict is updated in-memory even before save_index is called."""
    cache = ArticleCache(tmp_path)
    cache.write_article(
        slug="inline",
        title="Inline",
        category_path="X",
        content="c",
        lastmod="2024-01-01T00:00:00Z",
        article_id="i1",
        url="u",
    )
    # No save_index call — index should still be in memory
    results = cache.glob_articles("**")
    assert "inline" in results
