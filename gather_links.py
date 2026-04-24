#!/usr/bin/env python3
import json
import re
import subprocess
from pathlib import Path

SKIP = {"index.html", "colophon.html", "by-month.html"}


def git_log(filepath):
    result = subprocess.run(
        ["git", "log", "--format=%H|%aI|%s", "--follow", str(filepath)],
        capture_output=True,
        text=True,
    )
    commits = []
    for line in result.stdout.strip().splitlines():
        parts = line.split("|", 2)
        if len(parts) == 3:
            hash_, date, message = parts
            commits.append(
                {
                    "hash": hash_,
                    "date": date[:10],
                    "message": message,
                    "urls": re.findall(r"https?://\S+", message),
                }
            )
    return commits


def docs_description(slug):
    p = Path(f"{slug}.docs.md")
    if not p.exists():
        return ""
    for line in p.read_text().splitlines():
        if not line.startswith("<!--") and line.strip():
            return line.strip()
    return ""


def html_title(filepath):
    content = Path(filepath).read_text(errors="replace")
    m = re.search(r"<title>(.*?)</title>", content, re.IGNORECASE | re.DOTALL)
    return m.group(1).strip() if m else Path(filepath).stem


def main():
    html_files = [f for f in sorted(Path(".").glob("*.html")) if f.name not in SKIP]

    gathered = {}
    tools = []

    for f in html_files:
        commits = git_log(f)
        if not commits:
            continue
        slug = f.stem
        gathered[f.name] = commits
        tools.append(
            {
                "slug": slug,
                "title": html_title(f),
                "description": docs_description(slug),
                "created": commits[-1]["date"],
                "updated": commits[0]["date"],
                "url": f"/{slug}",
            }
        )

    Path("gathered_links.json").write_text(json.dumps(gathered, indent=2))
    tools.sort(key=lambda t: t["updated"], reverse=True)
    Path("tools.json").write_text(json.dumps(tools, indent=2))
    print(f"Wrote {len(tools)} tools")


if __name__ == "__main__":
    main()
