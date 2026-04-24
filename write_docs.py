#!/usr/bin/env python3
import subprocess
import sys
from pathlib import Path

DRY_RUN = "--dry-run" in sys.argv
VERBOSE = "--verbose" in sys.argv
SKIP = {"index", "colophon", "by-month"}
MODEL = "claude-haiku-4-5-20251001"
SYSTEM = (
    "Write a paragraph of documentation for this HTML tool page as markdown. "
    "Do not include any headings. Do not use the words 'just' or 'simply'. "
    "Keep it to 2-3 sentences."
)


def last_commit_hash(filepath):
    r = subprocess.run(
        ["git", "log", "-1", "--format=%H", str(filepath)],
        capture_output=True,
        text=True,
    )
    return r.stdout.strip()


def stored_hash(docs_path):
    if not docs_path.exists():
        return None
    for line in docs_path.read_text().splitlines():
        if line.startswith("<!-- Generated from commit:"):
            return line.split(":", 1)[1].strip().rstrip(" -->")
    return None


def main():
    updated = []
    for f in sorted(Path(".").glob("*.html")):
        if f.stem in SKIP:
            continue
        docs = Path(f"{f.stem}.docs.md")
        current = last_commit_hash(f)
        if current == stored_hash(docs):
            if VERBOSE:
                print(f"  skip {f.stem}")
            continue
        print(f"Generating docs for {f.stem}...")
        if DRY_RUN:
            continue
        result = subprocess.run(
            ["llm", "-m", MODEL, "--system", SYSTEM],
            input=f.read_text(errors="replace"),
            capture_output=True,
            text=True,
        )
        if result.returncode != 0:
            print(f"  ERROR: {result.stderr}", file=sys.stderr)
            continue
        docs.write_text(result.stdout.strip() + f"\n\n<!-- Generated from commit: {current} -->\n")
        updated.append(f.stem)
        print(f"  Wrote {docs}")
    print(f"\nUpdated {len(updated)} docs files")


if __name__ == "__main__":
    main()
