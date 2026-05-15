#!/usr/bin/env python3
import json
import re
import markdown
from pathlib import Path

PAGES_BASE = "https://schepens83.github.io/tools"

tools = json.loads(Path("tools.json").read_text())
readme = Path("README.md").read_text()

by_created = sorted(tools, key=lambda t: t["created"], reverse=True)[:5]
by_updated = sorted(tools, key=lambda t: t["updated"], reverse=True)[:5]
all_tools = sorted(tools, key=lambda t: t["title"])


def tool_li_html(t):
    return f'<li><a href="{t["url"]}">{t["title"]}</a></li>'


def tool_li_md(t):
    desc = f' — {t["description"]}' if t.get("description") else ""
    return f'- [{t["title"]}]({PAGES_BASE}/{t["url"]}){desc}'


recently_html = (
    "<h2>Recently added</h2>"
    "<ul>" + "".join(tool_li_html(t) for t in by_created) + "</ul>"
    "<h2>Recently updated</h2>"
    "<ul>" + "".join(tool_li_html(t) for t in by_updated) + "</ul>"
)

recently_md = (
    "\n\n### Recently added\n\n"
    + "\n".join(tool_li_md(t) for t in by_created)
    + "\n\n### Recently updated\n\n"
    + "\n".join(tool_li_md(t) for t in by_updated)
    + "\n\n"
)

tools_md = "\n\n" + "\n".join(tool_li_md(t) for t in all_tools) + "\n\n"


def replace_block(text, marker, content):
    pattern = rf"<!-- {marker} starts -->.*?<!-- {marker} stops -->"
    replacement = f"<!-- {marker} starts -->{content}<!-- {marker} stops -->"
    return re.sub(pattern, replacement, text, flags=re.DOTALL)


body = replace_block(
    markdown.markdown(readme, extensions=["tables", "fenced_code"]),
    "recently",
    recently_html,
)

readme_updated = replace_block(readme, "recently", recently_md)
readme_updated = replace_block(readme_updated, "tools", tools_md)

if readme_updated != readme:
    Path("README.md").write_text(readme_updated)
    print("Updated README.md")

html = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>schepens83/tools</title>
<style>
* {{ box-sizing: border-box; }}
body {{ font-family: system-ui, sans-serif; max-width: 800px; margin: 2rem auto; padding: 0 1rem; line-height: 1.6; color: #222; }}
a {{ color: #6200ea; }}
h1 {{ margin-bottom: 0.25rem; }}
#tool-search {{ border: 1px solid #ccc; border-radius: 4px; }}
#tool-search-results a {{ display: block; padding: 0.2rem 0; }}
</style>
</head>
<body>
{body}
<script type="module" src="homepage-search.js" data-tool-search></script>
</body>
</html>"""

Path("index.html").write_text(html)
print("Wrote index.html")
