#!/usr/bin/env python3
import json
from pathlib import Path

gathered = json.loads(Path("gathered_links.json").read_text())
dates = {fname: commits[0]["date"] for fname, commits in gathered.items() if commits}
Path("dates.json").write_text(json.dumps(dates, indent=2))
print(f"Wrote {len(dates)} entries to dates.json")
