"""Utilities for preparing content for Confluence storage."""

from __future__ import annotations

import re
from typing import Final

import markdown2

_HTML_TAG_RE: Final[re.Pattern[str]] = re.compile(r"<\s*[a-zA-Z][^>]*>")


def _looks_like_html(content: str) -> bool:
    """Return ``True`` when the content already appears to be HTML."""

    stripped = content.strip()
    if not stripped:
        return False
    return bool(_HTML_TAG_RE.search(stripped))


def to_confluence_storage(content: str) -> str:
    """Convert markdown content into HTML suitable for Confluence storage.

    Confluence expects the ``storage`` representation which accepts simple
    HTML.  The application allows callers to provide markdown when creating or
    updating a page.  This helper normalises the incoming content, only
    applying markdown conversion when the input does not already look like
    HTML.
    """

    if not content or not content.strip():
        return ""

    if _looks_like_html(content):
        return content

    return markdown2.markdown(content)

