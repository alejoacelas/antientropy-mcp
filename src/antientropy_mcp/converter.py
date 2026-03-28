"""HTML-to-Markdown converter for Document360 article content."""

from __future__ import annotations

import re
from typing import Any

from bs4 import BeautifulSoup
from markdownify import MarkdownConverter


# Map from CSS class name to default title when the title div is empty.
_CALLOUT_DEFAULTS: dict[str, str] = {
    "infoBox": "Info",
    "warningBox": "Warning",
    "errorBox": "Important",
}


class D360Converter(MarkdownConverter):
    """Markdownify subclass that handles Document360-specific HTML patterns."""

    class Options(MarkdownConverter.DefaultOptions):  # type: ignore[name-defined]
        heading_style = "ATX"
        bullets = "-"
        strip = ["script", "style"]

    # ------------------------------------------------------------------
    # Callout box handling
    # ------------------------------------------------------------------

    def convert_section(self, el: Any, text: str, **kwargs: Any) -> str:
        """Convert <section> elements, detecting D360 callout box classes."""
        css_classes: list[str] = el.get("class") or []

        for box_class, default_title in _CALLOUT_DEFAULTS.items():
            if box_class in css_classes:
                return self._render_callout(el, box_class, default_title)

        # Plain section — fall back to normal block handling (just return the
        # converted children, which markdownify has already processed in `text`).
        return text

    def _render_callout(self, section_el: Any, box_class: str, default_title: str) -> str:
        """Render a callout section as a Markdown blockquote."""
        title_div = section_el.find("div", class_="title")
        content_div = section_el.find("div", class_="content")

        # --- title ---
        if title_div is not None:
            raw_title = title_div.get_text(separator=" ", strip=True)
        else:
            raw_title = ""

        title = raw_title if raw_title else default_title

        # --- content ---
        if content_div is not None:
            # Convert the content subtree to markdown using the same converter.
            content_md = self.convert(str(content_div)).strip()
            # Remove the outer <div> tags that markdownify may leave (it
            # won't — convert() handles the whole fragment — but strip just
            # in case).
        else:
            content_md = ""

        # --- assemble blockquote ---
        lines: list[str] = [f"> **{title}:**"]
        if content_md:
            for line in content_md.splitlines():
                lines.append(f"> {line}" if line.strip() else ">")
        return "\n".join(lines) + "\n\n"


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def convert_article_html(html: str | None) -> str:
    """Convert an HTML article string to clean Markdown.

    Args:
        html: Raw HTML string, or None / empty string.

    Returns:
        Markdown string with no raw HTML tags remaining.
    """
    if not html:
        return ""

    # Pre-process: remove script and style content so their text nodes never
    # appear in the output (markdownify's `strip` option handles the tags but
    # BeautifulSoup decompose is safer for nested content).
    soup = BeautifulSoup(html, "html.parser")
    for tag in soup(["script", "style"]):
        tag.decompose()

    cleaned_html = str(soup)

    md = D360Converter().convert(cleaned_html)

    # Collapse excessive blank lines (> 2 consecutive newlines → 2).
    md = re.sub(r"\n{3,}", "\n\n", md)

    return md.strip()
