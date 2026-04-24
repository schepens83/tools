import re
from pathlib import Path

ROOT = Path(__file__).parent.parent
SKIP = {"index.html", "colophon.html", "by-month.html"}


def tool_files():
    return [f for f in ROOT.glob("*.html") if f.name not in SKIP]


def test_tools_exist():
    assert len(tool_files()) > 0, "No tool HTML files found"


def test_tools_have_title():
    for f in tool_files():
        content = f.read_text(errors="replace")
        assert re.search(r"<title>.+</title>", content, re.IGNORECASE), \
            f"{f.name} is missing a <title>"


def test_tools_have_charset():
    for f in tool_files():
        content = f.read_text(errors="replace")
        assert "charset" in content.lower(), f"{f.name} is missing charset meta tag"
