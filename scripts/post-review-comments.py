#!/usr/bin/env python3
"""
Post inline PR review comments for each file changed by the DeepWork review.

Reads /tmp/deepwork_changes.json (written by Claude) for per-change descriptions.
Falls back to a diff-based summary when the file is absent or an entry is missing.
Posts a single GitHub PR review with one inline comment per changed file.
"""

from __future__ import annotations

import json
import os
import re
import subprocess
import sys
from pathlib import Path
from typing import Any


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def run(cmd: list[str], **kwargs) -> subprocess.CompletedProcess:
    return subprocess.run(cmd, capture_output=True, text=True, **kwargs)


def get_head_sha() -> str:
    return run(["git", "rev-parse", "HEAD"]).stdout.strip()


def get_changed_files(base_ref: str) -> list[str]:
    """Return files changed between the base branch and HEAD."""
    # Try the exact remote ref first (available when the base branch was fetched).
    for ref in (f"origin/{base_ref}", base_ref, "HEAD~1"):
        result = run(["git", "diff", ref, "HEAD", "--name-only", "--diff-filter=ACMR"])
        if result.returncode == 0 and result.stdout.strip():
            return [f for f in result.stdout.splitlines() if f.strip()]
    return []


def get_diff(file_path: str, base_ref: str) -> str:
    for ref in (f"origin/{base_ref}", base_ref, "HEAD~1"):
        result = run(["git", "diff", ref, "HEAD", "--", file_path])
        if result.returncode == 0 and result.stdout.strip():
            return result.stdout
    return ""


def first_changed_line(diff: str) -> int:
    """
    Return the line number (in the new file) of the first added line.
    Parses unified diff hunk headers: @@ -old +new,count @@
    """
    current_new = 0
    for line in diff.splitlines():
        if line.startswith("@@"):
            m = re.search(r"\+(\d+)", line)
            if m:
                current_new = int(m.group(1))
        elif line.startswith("+") and not line.startswith("+++"):
            return max(current_new, 1)
        elif not line.startswith("-") and not line.startswith("\\"):
            current_new += 1
    return 1


def count_added_lines(diff: str) -> int:
    return sum(
        1
        for line in diff.splitlines()
        if line.startswith("+") and not line.startswith("+++")
    )


# ---------------------------------------------------------------------------
# Load Claude's change summary (optional)
# ---------------------------------------------------------------------------

def load_changes_by_file() -> dict[str, list[dict[str, Any]]]:
    changes_path = Path("/tmp/deepwork_changes.json")
    if not changes_path.exists():
        return {}
    try:
        data = json.loads(changes_path.read_text())
        by_file: dict[str, list[dict]] = {}
        for entry in data.get("changes", []):
            fp = entry.get("file", "").lstrip("./")
            by_file.setdefault(fp, []).append(entry)
        return by_file
    except (json.JSONDecodeError, OSError) as exc:
        print(f"Warning: could not parse /tmp/deepwork_changes.json: {exc}", file=sys.stderr)
        return {}


# ---------------------------------------------------------------------------
# Build comment body for a file
# ---------------------------------------------------------------------------

def build_comment_body(
    file_path: str,
    diff: str,
    changes: list[dict[str, Any]],
) -> str:
    if changes:
        bullets = "\n".join(
            f"- **{c.get('description', 'Change applied')}**"
            + (f"\n  *{c.get('reason', '')}*" if c.get("reason") else "")
            for c in changes
        )
        return (
            "🤖 **DeepWork Review** applied the following changes:\n\n"
            + bullets
        )
    # Fallback: diff statistics
    added = count_added_lines(diff)
    return (
        f"🤖 **DeepWork Review** applied {added} line(s) of changes to this file "
        f"based on review findings."
    )


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    pr_number = os.environ.get("PR_NUMBER", "")
    repo = os.environ.get("GITHUB_REPOSITORY", "")
    # GITHUB_BASE_REF is set automatically by GitHub Actions for pull_request events.
    base_ref = os.environ.get("GITHUB_BASE_REF", "main")

    if not pr_number or not repo:
        print("PR_NUMBER or GITHUB_REPOSITORY not set; skipping review comments.", file=sys.stderr)
        sys.exit(0)

    commit_sha = get_head_sha()
    changed_files = get_changed_files(base_ref)

    if not changed_files:
        print("No changed files found between base branch and HEAD; nothing to comment on.")
        sys.exit(0)

    changes_by_file = load_changes_by_file()

    inline_comments: list[dict[str, Any]] = []
    for file_path in changed_files:
        diff = get_diff(file_path, base_ref)
        if not diff.strip():
            continue

        line_number = first_changed_line(diff)
        normalised = file_path.lstrip("./")
        file_changes = changes_by_file.get(normalised, []) or changes_by_file.get(file_path, [])
        body = build_comment_body(file_path, diff, file_changes)

        inline_comments.append({
            "path": file_path,
            "line": line_number,
            "side": "RIGHT",
            "body": body,
        })

    if not inline_comments:
        print("No inline comments to post.")
        sys.exit(0)

    # Build the review payload
    review_body = (
        f"🤖 **DeepWork automated review** applied changes to "
        f"{len(inline_comments)} file(s).\n\n"
        "Review the inline comments below for details on each change."
    )
    review_payload: dict[str, Any] = {
        "commit_id": commit_sha,
        "body": review_body,
        "event": "COMMENT",
        "comments": inline_comments,
    }

    payload_path = Path("/tmp/deepwork_review_payload.json")
    payload_path.write_text(json.dumps(review_payload, indent=2))

    result = run([
        "gh", "api",
        f"repos/{repo}/pulls/{pr_number}/reviews",
        "--method", "POST",
        "--input", str(payload_path),
    ])

    if result.returncode != 0:
        print(f"Error posting PR review: {result.stderr}", file=sys.stderr)
        # Non-fatal: the changes are already committed; just warn.
        sys.exit(0)

    print(
        f"Posted PR review with {len(inline_comments)} inline comment(s) "
        f"on PR #{pr_number}."
    )


if __name__ == "__main__":
    main()
