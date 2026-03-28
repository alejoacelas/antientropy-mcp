"""Article cache: filesystem-backed storage for scraped articles."""

from __future__ import annotations

import fnmatch
import json
import re
from pathlib import Path
from typing import Any


_FRONTMATTER_SEP = "---"


class ArticleCache:
    """Manage a local cache of articles in Markdown with YAML frontmatter."""

    def __init__(self, cache_dir: Path) -> None:
        self._cache_dir = Path(cache_dir)
        self._articles_dir = self._cache_dir / "articles"
        self._articles_dir.mkdir(parents=True, exist_ok=True)
        # In-memory index: slug -> {title, category_path, lastmod, id, url}
        self._index: dict[str, dict[str, str]] = {}

    # ------------------------------------------------------------------
    # Writing
    # ------------------------------------------------------------------

    def write_article(
        self,
        slug: str,
        title: str,
        category_path: str,
        content: str,
        lastmod: str,
        article_id: str,
        url: str,
    ) -> None:
        """Write article to disk with YAML frontmatter and update in-memory index."""
        frontmatter = (
            f'{_FRONTMATTER_SEP}\n'
            f'title: "{title}"\n'
            f'slug: {slug}\n'
            f'id: {article_id}\n'
            f'category_path: "{category_path}"\n'
            f'url: "{url}"\n'
            f'lastmod: "{lastmod}"\n'
            f'{_FRONTMATTER_SEP}\n'
        )
        file_content = frontmatter + content
        article_path = self._articles_dir / f"{slug}.md"
        article_path.write_text(file_content, encoding="utf-8")

        self._index[slug] = {
            "title": title,
            "category_path": category_path,
            "lastmod": lastmod,
            "id": article_id,
            "url": url,
        }

    # ------------------------------------------------------------------
    # Index
    # ------------------------------------------------------------------

    def save_index(self) -> None:
        """Persist in-memory index to _index.json."""
        index_path = self._cache_dir / "_index.json"
        index_path.write_text(
            json.dumps(self._index, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )

    def load_index(self) -> dict[str, dict[str, str]]:
        """Load index from _index.json. Returns empty dict if file absent."""
        index_path = self._cache_dir / "_index.json"
        if not index_path.exists():
            return {}
        return json.loads(index_path.read_text(encoding="utf-8"))

    # ------------------------------------------------------------------
    # Reading
    # ------------------------------------------------------------------

    def read_article(self, slug: str, offset: int = 0, limit: int = 2000) -> str:
        """Return article content (no frontmatter) with cat -n style line numbers.

        offset and limit apply to content lines only (0-based offset).
        A header line with the title is prepended before the numbered lines.
        """
        article_path = self._articles_dir / f"{slug}.md"
        if not article_path.exists():
            return f"Error: article '{slug}' not found in cache."

        raw = article_path.read_text(encoding="utf-8")
        content_lines = _strip_frontmatter(raw).splitlines()

        # Retrieve title from in-memory index or fall back to index file
        meta = self._index.get(slug)
        if meta is None:
            loaded = self.load_index()
            meta = loaded.get(slug)
        title = meta["title"] if meta else slug

        # Apply offset/limit
        page = content_lines[offset : offset + limit]

        # Build cat -n style output (line numbers start at offset+1)
        numbered_lines = [
            f"{offset + i + 1}\t{line}" for i, line in enumerate(page)
        ]

        header = f"# {title}\n"
        return header + "\n".join(numbered_lines)

    # ------------------------------------------------------------------
    # Glob
    # ------------------------------------------------------------------

    def glob_articles(self, pattern: str = "**") -> str:
        """Match pattern against virtual paths and titles; return formatted string.

        Matching is done against:
        - virtual path: {category_path}/{slug}
        - slug alone
        - title alone

        Uses fnmatch semantics. ** matches everything.
        """
        entries = self._combined_index()

        results: list[str] = []
        for slug, meta in entries.items():
            category_path = meta.get("category_path", "")
            title = meta.get("title", slug)
            virtual_path = f"{category_path}/{slug}"

            if (
                fnmatch.fnmatch(virtual_path, pattern)
                or fnmatch.fnmatch(slug, pattern)
                or fnmatch.fnmatch(title, pattern)
            ):
                results.append(f"{slug}\t{title}\t[{category_path}]")

        if not results:
            return "No articles matched."
        return "\n".join(results)

    # ------------------------------------------------------------------
    # Grep
    # ------------------------------------------------------------------

    def grep_articles(
        self,
        pattern: str,
        case_insensitive: bool = False,
        context_lines: int = 0,
        head_limit: int = 50,
    ) -> str:
        """Regex search across article content (not frontmatter).

        Returns ripgrep-style output: slug:line_number:matching_line
        Context lines are emitted as slug:line_number-context_line.
        """
        flags = re.IGNORECASE if case_insensitive else 0
        try:
            compiled = re.compile(pattern, flags)
        except re.error as exc:
            return f"Error: invalid regex pattern: {exc}"

        output_lines: list[str] = []
        articles_dir = self._articles_dir

        for article_path in sorted(articles_dir.glob("*.md")):
            slug = article_path.stem
            raw = article_path.read_text(encoding="utf-8")
            content_lines = _strip_frontmatter(raw).splitlines()

            # Find matching line indices
            match_indices: set[int] = set()
            for idx, line in enumerate(content_lines):
                if compiled.search(line):
                    match_indices.add(idx)

            if not match_indices:
                continue

            # Collect lines to emit (with context)
            lines_to_emit: dict[int, bool] = {}  # idx -> is_match
            for idx in match_indices:
                lines_to_emit[idx] = True
                for delta in range(1, context_lines + 1):
                    if idx - delta >= 0:
                        lines_to_emit.setdefault(idx - delta, False)
                    if idx + delta < len(content_lines):
                        lines_to_emit.setdefault(idx + delta, False)

            for idx in sorted(lines_to_emit):
                line_num = idx + 1
                output_lines.append(f"{slug}:{line_num}:{content_lines[idx]}")

            if len(output_lines) >= head_limit:
                output_lines = output_lines[:head_limit]
                break

        if not output_lines:
            return "No matches found."
        return "\n".join(output_lines)

    # ------------------------------------------------------------------
    # Categories
    # ------------------------------------------------------------------

    def save_categories(self, tree: Any) -> None:
        """Persist category tree to _categories.json."""
        path = self._cache_dir / "_categories.json"
        path.write_text(
            json.dumps(tree, indent=2, ensure_ascii=False), encoding="utf-8"
        )

    def load_categories(self) -> Any:
        """Load category tree from _categories.json. Returns None if absent."""
        path = self._cache_dir / "_categories.json"
        if not path.exists():
            return None
        return json.loads(path.read_text(encoding="utf-8"))

    def format_category_tree(self) -> str:
        """Render category tree as indented text with article counts."""
        tree = self.load_categories()
        if tree is None:
            return "No categories cached."
        lines: list[str] = []
        _render_tree_node(tree, lines, indent=0)
        return "\n".join(lines)

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _combined_index(self) -> dict[str, dict[str, str]]:
        """Return in-memory index merged with persisted index (in-memory wins)."""
        merged = self.load_index()
        merged.update(self._index)
        return merged


# ---------------------------------------------------------------------------
# Module-level helpers
# ---------------------------------------------------------------------------


def _strip_frontmatter(text: str) -> str:
    """Remove YAML frontmatter delimited by --- lines and return body."""
    lines = text.splitlines()
    if not lines or lines[0].strip() != _FRONTMATTER_SEP:
        return text
    for i in range(1, len(lines)):
        if lines[i].strip() == _FRONTMATTER_SEP:
            # Return everything after the closing ---
            return "\n".join(lines[i + 1 :])
    return text


def _count_articles(node: dict[str, Any]) -> int:
    """Count leaf articles (categoryType == 0) under a node."""
    children = node.get("children", [])
    if not children:
        return 1 if node.get("categoryType") == 0 else 0
    return sum(_count_articles(c) for c in children)


def _render_tree_node(
    node: dict[str, Any], lines: list[str], indent: int
) -> None:
    """Recursively render a category tree node."""
    title = node.get("title", "")
    cat_type = node.get("categoryType")
    children = node.get("children", [])
    prefix = "  " * indent

    if cat_type in (1, 2) and title:
        # Category node — show article count
        count = _count_articles(node)
        count_str = f" ({count} articles)" if count else ""
        lines.append(f"{prefix}{title}{count_str}")
        for child in children:
            _render_tree_node(child, lines, indent + 1)
    elif cat_type == 0 and title:
        # Leaf article
        slug = node.get("slug", "")
        lines.append(f"{prefix}- {title}  [{slug}]")
    else:
        # Root container (no title) — just recurse
        for child in children:
            _render_tree_node(child, lines, indent)
