#!/usr/bin/env python3
"""Extract user-typed messages from Claude + Codex transcripts, grouped per project.

Modes:
  extract_why                  list all projects with msg counts
  extract_why --project NAME   dump filtered user messages for one project

Flags worth knowing:
  --with-context     include the assistant text that immediately preceded each
                     user message (recommended for WHY synthesis).
  --with-git-log     also include commit messages from the project's cwd, merged
                     chronologically with the transcript messages. Only valid
                     with --project.
  --since YYYY-MM-DD only include messages (and commits) from on or after DATE.
                     Use this to refresh a WHY.md against new activity.
  --backend          claude | codex | all (default: all)
"""
import json, re, sys, argparse, subprocess
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
DEFAULT_MAX_CONTEXT_CHARS = 800


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


def trim(text, max_chars):
    """Plain trim (no tag-strip), returns (text, truncated). Used for assistant context."""
    if not text:
        return "", False
    text = text.strip()
    if not text:
        return "", False
    if max_chars and len(text) > max_chars:
        dropped = len(text) - max_chars
        text = text[:max_chars].rstrip() + f"\n\n[…trimmed {dropped} chars]"
        return text, True
    return text, False


# ---------- Claude ----------

def _claude_user_text(rec):
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


def _claude_assistant_text(rec):
    """Return the last text block from an assistant record, or None."""
    if rec.get("type") != "assistant":
        return None
    msg = rec.get("message", {})
    c = msg.get("content")
    if isinstance(c, list):
        texts = [x.get("text", "") for x in c if x.get("type") == "text"]
        return texts[-1] if texts else None
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


def iter_claude(max_chars=DEFAULT_MAX_CHARS, with_context=False, max_ctx=DEFAULT_MAX_CONTEXT_CHARS, since=None):
    """Yield (cwd, jsonl, ts, text, src, trunc, ctx_text, ctx_trunc) per user msg."""
    if not CLAUDE_ROOT.exists():
        return
    for pdir in CLAUDE_ROOT.iterdir():
        if not pdir.is_dir():
            continue
        for jsonl in pdir.glob("*.jsonl"):
            cwd = _claude_resolve_cwd(jsonl)
            if not cwd:
                continue
            last_asst = None
            for line in jsonl.open():
                try:
                    rec = json.loads(line)
                except Exception:
                    continue
                asst_txt = _claude_assistant_text(rec)
                if asst_txt is not None:
                    last_asst = asst_txt
                    continue
                user_txt = _claude_user_text(rec)
                cleaned, truncated = clean(user_txt, max_chars=max_chars)
                if not cleaned:
                    continue
                ts = rec.get("timestamp") or rec.get("message", {}).get("timestamp") or ""
                if since and ts and ts < since:
                    last_asst = None
                    continue
                ctx_text, ctx_trunc = ("", False)
                if with_context and last_asst:
                    ctx_text, ctx_trunc = trim(last_asst, max_ctx)
                yield (cwd, jsonl, ts, cleaned, "claude", truncated, ctx_text, ctx_trunc)
                last_asst = None


# ---------- Codex ----------

def _codex_is_injected(text):
    s = text.lstrip()
    return any(s.startswith(p) for p in CODEX_INJECTED_PREFIXES)


def _codex_user_text(p):
    if p.get("type") != "message" or p.get("role") != "user":
        return None
    for c in p.get("content", []):
        if c.get("type") == "input_text":
            txt = c.get("text", "")
            if _codex_is_injected(txt):
                return None
            return txt
    return None


def _codex_assistant_text(p):
    if p.get("type") != "message" or p.get("role") != "assistant":
        return None
    texts = [c.get("text", "") for c in p.get("content", []) if c.get("type") == "output_text"]
    return texts[-1] if texts else None


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


def iter_codex(max_chars=DEFAULT_MAX_CHARS, with_context=False, max_ctx=DEFAULT_MAX_CONTEXT_CHARS, since=None):
    if not CODEX_ROOT.exists():
        return
    for jsonl in CODEX_ROOT.rglob("*.jsonl"):
        cwd = _codex_resolve_cwd(jsonl)
        if not cwd:
            continue
        last_asst = None
        for line in jsonl.open():
            try:
                rec = json.loads(line)
            except Exception:
                continue
            if rec.get("type") != "response_item":
                continue
            p = rec.get("payload", {})
            asst_txt = _codex_assistant_text(p)
            if asst_txt is not None:
                last_asst = asst_txt
                continue
            user_txt = _codex_user_text(p)
            cleaned, truncated = clean(user_txt, max_chars=max_chars)
            if not cleaned:
                continue
            ts = rec.get("timestamp", "")
            if since and ts and ts < since:
                last_asst = None
                continue
            ctx_text, ctx_trunc = ("", False)
            if with_context and last_asst:
                ctx_text, ctx_trunc = trim(last_asst, max_ctx)
            yield (cwd, jsonl, ts, cleaned, "codex", truncated, ctx_text, ctx_trunc)
            last_asst = None


# ---------- Git log ----------

def iter_git_log(cwd, since=None):
    """Yield (ts, text, 'git', short_hash, False, '', False) per commit in cwd."""
    if not Path(cwd).exists():
        return
    fmt = "%H%x00%aI%x00%s%x00%b%x1e"
    cmd = ["git", "-C", cwd, "log", f"--pretty=format:{fmt}"]
    if since:
        # git accepts ISO timestamps fine
        cmd.append(f"--since={since}")
    try:
        out = subprocess.check_output(cmd, text=True, stderr=subprocess.DEVNULL)
    except (subprocess.CalledProcessError, FileNotFoundError):
        return
    for raw in out.split("\x1e"):
        raw = raw.strip()
        if not raw:
            continue
        parts = raw.split("\x00")
        if len(parts) < 4:
            continue
        full_hash, ts, subject, body = parts[0], parts[1], parts[2], parts[3].strip()
        short = full_hash[:8]
        text = subject if not body else f"{subject}\n\n{body}"
        yield (ts, text, "git", short, False, "", False)


# ---------- Aggregation ----------

def collect(backends, max_chars=DEFAULT_MAX_CHARS, with_context=False, max_ctx=DEFAULT_MAX_CONTEXT_CHARS, since=None):
    by_cwd = defaultdict(list)
    if "claude" in backends:
        for cwd, jsonl, ts, text, src, trunc, ctx, ctx_trunc in iter_claude(max_chars, with_context, max_ctx, since=since):
            by_cwd[cwd].append((ts, text, src, jsonl.name, trunc, ctx, ctx_trunc))
    if "codex" in backends:
        for cwd, jsonl, ts, text, src, trunc, ctx, ctx_trunc in iter_codex(max_chars, with_context, max_ctx, since=since):
            by_cwd[cwd].append((ts, text, src, jsonl.name, trunc, ctx, ctx_trunc))
    for cwd in by_cwd:
        by_cwd[cwd].sort(key=lambda m: (m[0] or "", m[3]))
    return by_cwd


def cmd_list(args):
    by_cwd = collect(args.backends, max_chars=args.max_msg_chars,
                     with_context=args.with_context, max_ctx=args.max_context_chars,
                     since=args.since)
    rows = []
    for cwd, msgs in by_cwd.items():
        chars = sum(len(m[1]) for m in msgs)
        ctx_chars = sum(len(m[5]) for m in msgs)
        trunc = sum(1 for m in msgs if m[4])
        ctx_trunc = sum(1 for m in msgs if m[6])
        srcs = sorted({m[2] for m in msgs})
        rows.append((cwd, len(msgs), chars, ctx_chars, trunc, ctx_trunc, ",".join(srcs)))
    rows.sort(key=lambda r: -(r[2] + r[3]))
    if args.with_context:
        print(f"{'cwd':<60} {'msgs':>6} {'usr_ch':>8} {'ctx_ch':>8} {'u_tr':>4} {'c_tr':>4} {'sources':<12}")
        for cwd, n, ch, cch, tr, ctr, srcs in rows:
            print(f"{cwd:<60} {n:>6} {ch:>8} {cch:>8} {tr:>4} {ctr:>4} {srcs:<12}")
    else:
        print(f"{'cwd':<60} {'msgs':>6} {'chars':>9} {'trunc':>6} {'sources':<12}")
        for cwd, n, ch, _cch, tr, _ctr, srcs in rows:
            print(f"{cwd:<60} {n:>6} {ch:>9} {tr:>6} {srcs:<12}")
    print()
    print(f"projects with content:   {len(rows)}")
    print(f"total user msgs:         {sum(r[1] for r in rows)}")
    total_chars = sum(r[2] for r in rows)
    total_ctx = sum(r[3] for r in rows)
    print(f"total user chars:        {total_chars:,}  (~{total_chars//4:,} tokens)")
    if args.with_context:
        print(f"total context chars:     {total_ctx:,}  (~{total_ctx//4:,} tokens)")
        print(f"combined:                {total_chars+total_ctx:,}  (~{(total_chars+total_ctx)//4:,} tokens)")
    print(f"user msgs truncated:     {sum(r[4] for r in rows)}  (cap = {args.max_msg_chars} chars)")
    if args.with_context:
        print(f"context blocks truncated:{sum(r[5] for r in rows)}  (cap = {args.max_context_chars} chars)")


def cmd_project(args):
    by_cwd = collect(args.backends, max_chars=args.max_msg_chars,
                     with_context=args.with_context, max_ctx=args.max_context_chars,
                     since=args.since)
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
    msgs = list(by_cwd[cwd])

    git_count = 0
    if args.with_git_log:
        for git_msg in iter_git_log(cwd, since=args.since):
            ts, text, src, short, trunc, ctx, ctx_trunc = git_msg
            msgs.append((ts, text, src, short, trunc, ctx, ctx_trunc))
            git_count += 1
        msgs.sort(key=lambda m: (m[0] or "", m[3]))

    trunc = sum(1 for m in msgs if m[4])
    ctx_trunc = sum(1 for m in msgs if m[6])
    print(f"# Filtered messages for: {cwd}")
    print(f"# {len(msgs)} messages, sources: {sorted({m[2] for m in msgs})}")
    print(f"# {trunc} message(s) truncated at {args.max_msg_chars} chars")
    if args.with_context:
        with_ctx = sum(1 for m in msgs if m[5])
        print(f"# {with_ctx} message(s) with assistant context ({ctx_trunc} ctx truncated at {args.max_context_chars} chars)")
    if args.with_git_log:
        print(f"# {git_count} git commit(s) included")
    if args.since:
        print(f"# filtered to messages on/after {args.since}")
    print()
    for ts, text, src, fname, _trunc, ctx, _ctx_trunc in msgs:
        print(f"## [{ts or '?'}] ({src}) {fname}")
        print()
        if ctx:
            print("> **assistant said:**")
            for ln in ctx.splitlines():
                print(f"> {ln}")
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
        help=f"trim each user message at N chars (default: {DEFAULT_MAX_CHARS})",
    )
    ap.add_argument(
        "--with-context",
        action="store_true",
        help="prepend the immediately-preceding assistant text to each user message",
    )
    ap.add_argument(
        "--max-context-chars",
        type=int,
        default=DEFAULT_MAX_CONTEXT_CHARS,
        help=f"trim each assistant context block at N chars (default: {DEFAULT_MAX_CONTEXT_CHARS})",
    )
    ap.add_argument(
        "--with-git-log",
        action="store_true",
        help="also include commit messages from the project's cwd (only with --project)",
    )
    ap.add_argument(
        "--since",
        default=None,
        help="filter messages and commits to those on/after ISO date (e.g. 2026-05-01)",
    )
    args = ap.parse_args()
    args.backends = {"claude", "codex"} if args.backend == "all" else {args.backend}
    if args.with_git_log and not args.project:
        print("--with-git-log requires --project", file=sys.stderr)
        sys.exit(2)
    if args.project:
        cmd_project(args)
    else:
        cmd_list(args)


if __name__ == "__main__":
    main()
