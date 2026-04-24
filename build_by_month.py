#!/usr/bin/env python3
import json
from collections import defaultdict
from pathlib import Path

gathered = json.loads(Path("gathered_links.json").read_text())


def description(slug):
    p = Path(f"{slug}.docs.md")
    if not p.exists():
        return ""
    for line in p.read_text().splitlines():
        if not line.startswith("<!--") and line.strip():
            words = line.strip().split()
            return " ".join(words[:30]) + ("…" if len(words) > 30 else "")
    return ""


by_month = defaultdict(list)
for fname, commits in gathered.items():
    if not commits:
        continue
    slug = fname.replace(".html", "")
    by_month[commits[-1]["date"][:7]].append(
        {"slug": slug, "description": description(slug), "date": commits[-1]["date"]}
    )

sections = []
for month in sorted(by_month.keys(), reverse=True):
    items = sorted(by_month[month], key=lambda t: t["date"])
    lis = "".join(
        f'<li><a href="{t["slug"]}.html">{t["slug"]}</a>'
        + (f' — {t["description"]}' if t["description"] else "")
        + "</li>"
        for t in items
    )
    sections.append(f"<h2>{month}</h2><ul>{lis}</ul>")

html = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>By month — schepens83/tools</title>
<style>
* {{ box-sizing: border-box; }}
body {{ font-family: system-ui, sans-serif; max-width: 800px; margin: 2rem auto; padding: 0 1rem; line-height: 1.6; color: #222; }}
a {{ color: #6200ea; }}
</style>
</head>
<body>
<h1>Tools by month</h1>
<p><a href="index.html">← Home</a></p>
{"".join(sections)}
</body>
</html>"""

Path("by-month.html").write_text(html)
print("Wrote by-month.html")
