#!/usr/bin/env python3
import json
from pathlib import Path

redirects = json.loads(Path("_redirects.json").read_text())
for slug, target in redirects.items():
    Path(f"{slug}.html").write_text(
        f"""<!DOCTYPE html>
<html>
<head>
<meta http-equiv="refresh" content="0; url={target}">
<title>Redirecting…</title>
</head>
<body><p>Redirecting to <a href="{target}">{target}</a>…</p></body>
</html>"""
    )
    print(f"  {slug}.html → {target}")
