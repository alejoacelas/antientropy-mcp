"""Tests for the HTML-to-Markdown converter."""

import re
from pathlib import Path

import pytest

from antientropy_mcp.converter import convert_article_html


FIXTURE_DIR = Path(__file__).parent / "fixtures"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def has_raw_html(text: str) -> bool:
    """Return True if text contains any HTML tags."""
    return bool(re.search(r"<[a-zA-Z/][^>]*>", text))


# ---------------------------------------------------------------------------
# Edge cases
# ---------------------------------------------------------------------------

def test_none_input_returns_empty_string():
    assert convert_article_html(None) == ""


def test_empty_string_returns_empty_string():
    assert convert_article_html("") == ""


# ---------------------------------------------------------------------------
# Basic HTML elements
# ---------------------------------------------------------------------------

def test_headings_converted():
    html = "<h1>Title</h1><h2>Subtitle</h2><h3>Section</h3>"
    md = convert_article_html(html)
    assert "# Title" in md
    assert "## Subtitle" in md
    assert "### Section" in md


def test_unordered_list_converted():
    html = "<ul><li>Alpha</li><li>Beta</li></ul>"
    md = convert_article_html(html)
    assert "- Alpha" in md
    assert "- Beta" in md


def test_ordered_list_converted():
    html = "<ol><li>First</li><li>Second</li></ol>"
    md = convert_article_html(html)
    assert "1." in md
    assert "First" in md
    assert "Second" in md


def test_links_preserved():
    html = '<p>See <a href="https://example.com">example</a> here.</p>'
    md = convert_article_html(html)
    assert "[example](https://example.com)" in md


def test_no_raw_html_tags_in_basic_output():
    html = "<h2>Hello</h2><p>World <strong>bold</strong></p>"
    md = convert_article_html(html)
    assert not has_raw_html(md)


# ---------------------------------------------------------------------------
# Callout boxes
# ---------------------------------------------------------------------------

def test_infobox_with_title():
    html = (
        '<section class="infoBox">'
        '<div class="title">Note</div>'
        '<div class="content"><p>Important info</p></div>'
        "</section>"
    )
    md = convert_article_html(html)
    assert "> **Note:**" in md
    assert "Important info" in md
    # Content should be quoted
    assert md.count(">") >= 1
    assert not has_raw_html(md)


def test_warningbox_with_title():
    html = (
        '<section class="warningBox">'
        '<div class="title">Warning</div>'
        '<div class="content"><p>Be careful</p></div>'
        "</section>"
    )
    md = convert_article_html(html)
    assert "> **Warning:**" in md
    assert "Be careful" in md
    assert not has_raw_html(md)


def test_errorbox_with_title():
    html = (
        '<section class="errorBox">'
        '<div class="title">Error</div>'
        '<div class="content"><p>Something broke</p></div>'
        "</section>"
    )
    md = convert_article_html(html)
    assert "> **Error:**" in md
    assert "Something broke" in md
    assert not has_raw_html(md)


def test_infobox_empty_title_uses_default():
    html = (
        '<section class="infoBox">'
        '<div class="title"></div>'
        '<div class="content"><p>Details here</p></div>'
        "</section>"
    )
    md = convert_article_html(html)
    assert "> **Info:**" in md
    assert "Details here" in md


def test_warningbox_empty_title_uses_default():
    html = (
        '<section class="warningBox">'
        '<div class="title"></div>'
        '<div class="content"><p>Be careful</p></div>'
        "</section>"
    )
    md = convert_article_html(html)
    assert "> **Warning:**" in md


def test_errorbox_empty_title_uses_default():
    html = (
        '<section class="errorBox">'
        '<div class="title"></div>'
        '<div class="content"><p>Critical</p></div>'
        "</section>"
    )
    md = convert_article_html(html)
    assert "> **Important:**" in md


def test_infobox_title_from_heading_tag():
    """Title div may contain an h3 tag rather than plain text."""
    html = (
        '<section class="infoBox">'
        '<div class="title"><h3>Who is this for?</h3></div>'
        '<div class="content"><p>Everyone</p></div>'
        "</section>"
    )
    md = convert_article_html(html)
    assert "> **Who is this for?:**" in md
    assert "Everyone" in md
    assert not has_raw_html(md)


# ---------------------------------------------------------------------------
# Script / style stripping
# ---------------------------------------------------------------------------

def test_script_tags_stripped():
    html = "<p>Hello</p><script>alert('x')</script>"
    md = convert_article_html(html)
    assert "alert" not in md
    assert not has_raw_html(md)


def test_style_tags_stripped():
    html = "<p>Hello</p><style>.foo { color: red; }</style>"
    md = convert_article_html(html)
    assert "color" not in md
    assert not has_raw_html(md)


# ---------------------------------------------------------------------------
# Real fixture
# ---------------------------------------------------------------------------

def test_fixture_converts_without_raw_html():
    html = (FIXTURE_DIR / "sample_article.html").read_text()
    md = convert_article_html(html)
    assert md.strip() != ""
    assert not has_raw_html(md), f"Raw HTML tags found in output:\n{md}"


def test_fixture_contains_expected_content():
    html = (FIXTURE_DIR / "sample_article.html").read_text()
    md = convert_article_html(html)
    # Headings from fixture
    assert "Personal Data" in md
    # Callout box with title derived from h3 heading
    assert "Who is this article for?" in md
    # Warning box (empty title → default)
    assert "> **Warning:**" in md
    # Links present
    assert "https://" in md
