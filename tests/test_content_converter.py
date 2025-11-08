"""Unit tests for the markdown-to-storage converter."""

from conflagent_core.content import to_confluence_storage


def test_converts_markdown_heading():
    content = "# Title"

    converted = to_confluence_storage(content)

    assert "<h1>Title</h1>" in converted


def test_leaves_html_untouched():
    html = "<p>Already formatted</p>"

    converted = to_confluence_storage(html)

    assert converted == html


def test_handles_plain_text():
    content = "Simple text"

    converted = to_confluence_storage(content)

    assert converted.startswith("<p>")
    assert "Simple text" in converted


def test_empty_content_returns_empty_string():
    assert to_confluence_storage("") == ""
    assert to_confluence_storage("   ") == ""
