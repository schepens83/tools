#!/usr/bin/env python3
"""Extract real user-typed messages from Claude transcripts, grouped per project.

Modes:
  extract_why.py                 list all projects with msg counts (resolved cwd)
  extract_why.py --project PATH  dump filtered user messages for one project to stdout
  extract_why.py --project NAME  fuzzy match on cwd substring (e.g. 'whisper-dictate')
"""
import json, re, sys, argparse
from pathlib import Path
from collections import defaultdict

ROOT = Path.home() / ".claude" / "projects"
TAG_RE = re.compile(
    r"<(system-reminder|command-name|command-message|command-args|"
    r"local-command-stdout|local-command-stderr|local-command-caveat)>.*?</\1>",
    re.DOTALL,
)
EMPTY_CMD_RE = re.compile(r"^\s*(/\w[\w-]*)\s*$")


def extract_text(rec):
    if rec.get("type") != "user":
        return None
    # Skip system-injected pseudo-user records (skill bodies, tool meta, etc.)
    if rec.get("isMeta") or rec.get("sourceToolUseID"):
        return None
    msg = rec.get("message", {})
    c = msg.get("content")
    if isinstance(c, str):
        return c
    if isinstance(c, list):
        parts = []
        for x in c:
            if x.get("type") == "text":
                parts.append(x.get("text", ""))
            elif x.get("type") == "tool_result":
                return None
        return "\n".join(parts) if parts else None
    return None


def clean(text):
    if not text:
        return ""
    text = TAG_RE.sub("", text).strip()
    if not text or EMPTY_CMD_RE.match(text):
        return ""
    return text


def resolve_cwd(jsonl_path):
    """Return the cwd recorded inside the JSONL (preserves dashes etc)."""
    try:
        with jsonl_path.open() as f:
            for line in f:
                try:
                    rec = json.loads(line)
                except Exception:
                    continue
                if rec.get("cwd"):
                    return rec["cwd"]
    except Exception:
        pass
    return None


def index_projects():
    """Group JSONL files by their real cwd. Returns {cwd: [Path, ...]}."""
    index = defaultdict(list)
    unresolved = []
    for pdir in ROOT.iterdir():
        if not pdir.is_dir():
            continue
        for jsonl in pdir.glob("*.jsonl"):
            cwd = resolve_cwd(jsonl)
            if cwd:
                index[cwd].append(jsonl)
            else:
                unresolved.append(jsonl)
    return index, unresolved


def collect_messages(jsonl_paths):
    """Yield (jsonl_name, timestamp, cleaned_text) tuples in file+line order."""
    msgs = []
    raw_lines = 0
    for jsonl in jsonl_paths:
        for line in jsonl.open():
            raw_lines += 1
            try:
                rec = json.loads(line)
            except Exception:
                continue
            txt = extract_text(rec)
            cleaned = clean(txt)
            if cleaned:
                ts = rec.get("timestamp") or rec.get("message", {}).get("timestamp") or ""
                msgs.append((jsonl.name, ts, cleaned))
    msgs.sort(key=lambda m: (m[1] or "", m[0]))
    return msgs, raw_lines


def cmd_list(args):
    index, unresolved = index_projects()
    rows = []
    for cwd, files in index.items():
        msgs, raw = collect_messages(files)
        if not msgs:
            continue
        chars = sum(len(m[2]) for m in msgs)
        rows.append((cwd, len(msgs), chars, raw, len(files)))
    rows.sort(key=lambda r: -r[2])
    print(f"{'cwd':<60} {'msgs':>6} {'chars':>9} {'raw':>7} {'files':>5}")
    for cwd, n, ch, raw, nf in rows:
        print(f"{cwd:<60} {n:>6} {ch:>9} {raw:>7} {nf:>5}")
    print()
    print(f"projects with content: {len(rows)}")
    print(f"total user msgs:       {sum(r[1] for r in rows)}")
    total_chars = sum(r[2] for r in rows)
    print(f"total chars:           {total_chars:,}  (~{total_chars//4:,} tokens)")
    if unresolved:
        print(f"unresolved jsonl files (no cwd):  {len(unresolved)}")


def cmd_project(args):
    target = args.project
    index, _ = index_projects()

    # exact path match first, then unique substring match
    candidates = [cwd for cwd in index if cwd == target]
    if not candidates:
        candidates = [cwd for cwd in index if target in cwd]

    if not candidates:
        print(f"no project matching: {target}", file=sys.stderr)
        print("hint: run without args to list available cwds", file=sys.stderr)
        sys.exit(1)
    if len(candidates) > 1:
        print(f"ambiguous match for '{target}':", file=sys.stderr)
        for c in candidates:
            print(f"  {c}", file=sys.stderr)
        sys.exit(2)

    cwd = candidates[0]
    msgs, raw = collect_messages(index[cwd])
    print(f"# Filtered user messages for: {cwd}")
    print(f"# {len(msgs)} messages from {len(index[cwd])} session file(s), {raw} raw lines")
    print()
    for fname, ts, text in msgs:
        header = f"## [{ts or '?'}] {fname}"
        print(header)
        print()
        print(text)
        print()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--project", help="cwd path or substring of one project to dump")
    args = ap.parse_args()
    if args.project:
        cmd_project(args)
    else:
        cmd_list(args)


if __name__ == "__main__":
    main()
