#!/usr/bin/env python3
import json
import re
from pathlib import Path

gathered = json.loads(Path("gathered_links.json").read_text())
GITHUB = "https://github.com/schepens83/tools"


def linkify(text):
    return re.sub(r"(https?://\S+)", r'<a href="\1">\1</a>', text)


def description(slug):
    p = Path(f"{slug}.docs.md")
    if not p.exists():
        return ""
    for line in p.read_text().splitlines():
        if not line.startswith("<!--") and line.strip():
            return line.strip()
    return ""


items = sorted(
    gathered.items(),
    key=lambda kv: kv[1][0]["date"] if kv[1] else "",
    reverse=True,
)

rows = []
for fname, commits in items:
    if not commits:
        continue
    slug = fname.replace(".html", "")
    desc = description(slug)
    commit_lis = "".join(
        f'<li>{c["date"]} — {linkify(c["message"])} '
        f'(<a href="{GITHUB}/commit/{c["hash"]}">commit</a>)</li>'
        for c in commits
    )
    rows.append(
        f'<section id="{slug}">'
        f'<h2><a href="/{slug}">{slug}</a> '
        f'<small>(<a href="{GITHUB}/blob/main/{fname}">source</a>)</small></h2>'
        + (f"<p>{desc}</p>" if desc else "")
        + f"<details><summary>{len(commits)} commit{'s' if len(commits) != 1 else ''}</summary>"
        f"<ul>{commit_lis}</ul></details>"
        f"</section>"
    )

html = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Colophon — schepens83/tools</title>
<style>
* {{ box-sizing: border-box; }}
body {{ font-family: system-ui, sans-serif; max-width: 800px; margin: 2rem auto; padding: 0 1rem; line-height: 1.6; color: #222; }}
a {{ color: #6200ea; }}
section {{ border-bottom: 1px solid #eee; padding: 1rem 0; }}
details {{ margin-top: 0.5rem; font-size: 0.9rem; }}
small {{ font-weight: normal; font-size: 0.8rem; }}
</style>
</head>
<body>
<h1>Colophon</h1>
<p><a href="/">← Home</a></p>
<p>{len(rows)} tools and their full commit histories.</p>
{"".join(rows)}
</body>
</html>"""

Path("colophon.html").write_text(html)
print(f"Wrote colophon.html with {len(rows)} tools")
