#!/usr/bin/env python3
"""Extract real user-typed messages from Claude + Codex transcripts, grouped per project.

Modes:
  extract_business_context.py                 list all projects with msg counts
  extract_business_context.py --project NAME  dump filtered user messages for one project
  extract_business_context.py --backend claude|codex|all   (default: all)
"""
import json, re, sys, argparse
from pathlib import Path
from collections import defaultdict

CLAUDE_ROOT = Path.home() / ".claude" / "projects"
CODEX_ROOT = Path.home() / ".codex" / "sessions"

TAG_RE = re.compile(
    r"<(system-reminder|command-name|command-message|command-args|"
    r"local-command-stdout|local-command-stderr|local-command-caveat)>.*?</\1>",
    re.DOTALL,
)
EMPTY_CMD_RE = re.compile(r"^\s*(/\w[\w-]*)\s*$")

# Codex auto-injects these as user-role content at session start / per turn
CODEX_INJECTED_PREFIXES = (
    "# AGENTS.md instructions",
    "<permissions instructions>",
    "<user_instructions>",
    "<environment_context>",
    "<system_prompt>",
    "<turn_aborted>",
    "<skill>",
    "<skill ",
)


DEFAULT_MAX_CHARS = 1500


def clean(text, max_chars=DEFAULT_MAX_CHARS):
    """Return (cleaned_text, was_truncated). Empty string means filtered out."""
    if not text:
        return "", False
    text = TAG_RE.sub("", text).strip()
    if not text or EMPTY_CMD_RE.match(text):
        return "", False
    truncated = False
    if max_chars and len(text) > max_chars:
        dropped = len(text) - max_chars
        text = text[:max_chars].rstrip() + f"\n\n[…trimmed {dropped} chars of pasted content]"
        truncated = True
    return text, truncated


# ---------- Claude ----------

def _claude_extract_text(rec):
    if rec.get("type") != "user":
        return None
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


def _claude_resolve_cwd(jsonl_path):
    try:
        for line in jsonl_path.open():
            try:
                rec = json.loads(line)
            except Exception:
                continue
            if rec.get("cwd"):
                return rec["cwd"]
    except Exception:
        pass
    return None


def iter_claude(max_chars=DEFAULT_MAX_CHARS):
    """Yield (cwd, jsonl_path, timestamp, cleaned_text, 'claude', truncated)."""
    if not CLAUDE_ROOT.exists():
        return
    for pdir in CLAUDE_ROOT.iterdir():
        if not pdir.is_dir():
            continue
        for jsonl in pdir.glob("*.jsonl"):
            cwd = _claude_resolve_cwd(jsonl)
            if not cwd:
                continue
            for line in jsonl.open():
                try:
                    rec = json.loads(line)
                except Exception:
                    continue
                txt = _claude_extract_text(rec)
                cleaned, truncated = clean(txt, max_chars=max_chars)
                if cleaned:
                    ts = rec.get("timestamp") or rec.get("message", {}).get("timestamp") or ""
                    yield (cwd, jsonl, ts, cleaned, "claude", truncated)


# ---------- Codex ----------

def _codex_is_injected(text):
    s = text.lstrip()
    return any(s.startswith(p) for p in CODEX_INJECTED_PREFIXES)


def _codex_resolve_cwd(jsonl_path):
    try:
        for line in jsonl_path.open():
            try:
                rec = json.loads(line)
            except Exception:
                continue
            if rec.get("type") == "session_meta":
                return rec.get("payload", {}).get("cwd")
    except Exception:
        pass
    return None


def iter_codex(max_chars=DEFAULT_MAX_CHARS):
    """Yield (cwd, jsonl_path, timestamp, cleaned_text, 'codex', truncated)."""
    if not CODEX_ROOT.exists():
        return
    for jsonl in CODEX_ROOT.rglob("*.jsonl"):
        cwd = _codex_resolve_cwd(jsonl)
        if not cwd:
            continue
        for line in jsonl.open():
            try:
                rec = json.loads(line)
            except Exception:
                continue
            if rec.get("type") != "response_item":
                continue
            p = rec.get("payload", {})
            if p.get("type") != "message" or p.get("role") != "user":
                continue
            for c in p.get("content", []):
                if c.get("type") != "input_text":
                    continue
                txt = c.get("text", "")
                if _codex_is_injected(txt):
                    continue
                cleaned, truncated = clean(txt, max_chars=max_chars)
                if cleaned:
                    yield (cwd, jsonl, rec.get("timestamp", ""), cleaned, "codex", truncated)


# ---------- Aggregation ----------

def collect(backends, max_chars=DEFAULT_MAX_CHARS):
    """Group messages by cwd. Returns {cwd: [(ts, text, source, jsonl_name, truncated)]}."""
    by_cwd = defaultdict(list)
    if "claude" in backends:
        for cwd, jsonl, ts, text, src, trunc in iter_claude(max_chars=max_chars):
            by_cwd[cwd].append((ts, text, src, jsonl.name, trunc))
    if "codex" in backends:
        for cwd, jsonl, ts, text, src, trunc in iter_codex(max_chars=max_chars):
            by_cwd[cwd].append((ts, text, src, jsonl.name, trunc))
    for cwd in by_cwd:
        by_cwd[cwd].sort(key=lambda m: (m[0] or "", m[3]))
    return by_cwd


def cmd_list(args):
    by_cwd = collect(args.backends, max_chars=args.max_msg_chars)
    rows = []
    for cwd, msgs in by_cwd.items():
        chars = sum(len(m[1]) for m in msgs)
        trunc = sum(1 for m in msgs if m[4])
        srcs = sorted({m[2] for m in msgs})
        rows.append((cwd, len(msgs), chars, trunc, ",".join(srcs)))
    rows.sort(key=lambda r: -r[2])
    print(f"{'cwd':<60} {'msgs':>6} {'chars':>9} {'trunc':>6} {'sources':<12}")
    for cwd, n, ch, tr, srcs in rows:
        print(f"{cwd:<60} {n:>6} {ch:>9} {tr:>6} {srcs:<12}")
    print()
    print(f"projects with content:   {len(rows)}")
    print(f"total user msgs:         {sum(r[1] for r in rows)}")
    total_chars = sum(r[2] for r in rows)
    print(f"total chars:             {total_chars:,}  (~{total_chars//4:,} tokens)")
    print(f"messages truncated:      {sum(r[3] for r in rows)}  (cap = {args.max_msg_chars} chars)")


def cmd_project(args):
    by_cwd = collect(args.backends, max_chars=args.max_msg_chars)
    target = args.project
    candidates = [c for c in by_cwd if c == target]
    if not candidates:
        candidates = [c for c in by_cwd if target in c]
    if not candidates:
        print(f"no project matching: {target}", file=sys.stderr)
        sys.exit(1)
    if len(candidates) > 1:
        print(f"ambiguous match for '{target}':", file=sys.stderr)
        for c in candidates:
            print(f"  {c}", file=sys.stderr)
        sys.exit(2)
    cwd = candidates[0]
    msgs = by_cwd[cwd]
    trunc = sum(1 for m in msgs if m[4])
    print(f"# Filtered user messages for: {cwd}")
    print(f"# {len(msgs)} messages, sources: {sorted({m[2] for m in msgs})}")
    print(f"# {trunc} message(s) truncated at {args.max_msg_chars} chars")
    print()
    for ts, text, src, fname, _ in msgs:
        print(f"## [{ts or '?'}] ({src}) {fname}")
        print()
        print(text)
        print()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--project", help="cwd path or substring of one project to dump")
    ap.add_argument(
        "--backend",
        choices=["claude", "codex", "all"],
        default="all",
        help="which transcript source(s) to read (default: all)",
    )
    ap.add_argument(
        "--max-msg-chars",
        type=int,
        default=DEFAULT_MAX_CHARS,
        help=f"trim each message at N chars (default: {DEFAULT_MAX_CHARS}; raise to keep more)",
    )
    args = ap.parse_args()
    args.backends = {"claude", "codex"} if args.backend == "all" else {args.backend}
    if args.project:
        cmd_project(args)
    else:
        cmd_list(args)


if __name__ == "__main__":
    main()
