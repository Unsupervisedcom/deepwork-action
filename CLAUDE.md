# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this repo is

A **composite GitHub Action** (not a JS/TS/Docker action) that runs Claude Code with the DeepWork plugin against a Pull Request, applies every review suggestion as code changes, auto-commits them to the PR branch, and posts inline PR review comments. There is no build system, no package manager, no test suite — the entire action is defined in `action.yml`, one prompt file, and one Python script.

## Repository layout

- `action.yml` — the composite action definition. All orchestration lives here.
- `prompts/review.txt` — the prompt fed to Claude Code via `claude-code-base-action`. Starts with `/review` to trigger the DeepWork plugin's review skill, then enforces CI-mode rules (no `AskUserQuestion`, apply every finding, write change log to `/tmp/deepwork_changes.json`).
- `scripts/post-review-comments.py` — runs **after** Claude finishes. Reads `/tmp/deepwork_changes.json`, diffs against the base branch, and POSTs a single PR review with one inline comment per changed file via `gh api`.
- `.github/workflows/example.yml` — reference workflow showing how downstream repos consume this action. Not a CI workflow for *this* repo.
- `.deepwork/` — DeepWork plugin's local state (`job.schema.json`, `tmp/status`). The `tmp/` subdirectory is what the action caches between runs.

## End-to-end flow (read this before changing anything)

The action's steps in `action.yml` form a pipeline that hands state between three different processes via well-known files. Breaking any link silently degrades the action — most failures here are silent because the Python step is non-fatal.

1. **Checkout + cache restore** — the consuming workflow checks out the PR head branch with `fetch-depth: 0`. The action restores `.deepwork/tmp` from the GitHub Actions cache, keyed on PR number. This is how already-passed reviews skip re-running on subsequent commits (the major token saver called out in the README).
2. **Fetch base branch** — `git fetch origin <base_ref> --depth=1` so the diff in step 5 has something to compare against. Failure here is logged but non-fatal.
3. **Cleanup** — deletes any stale `/tmp/deepwork_changes.json` from a previous run on the same runner.
4. **Run Claude Code** — invokes `anthropics/claude-code-base-action@beta` with:
   - `prompt_file: prompts/review.txt`
   - `plugin_marketplaces: https://github.com/Unsupervisedcom/deepwork.git`
   - `plugins: deepwork@deepwork-plugins`
   - `claude_args: --dangerously-skip-permissions --model <model> --max-turns <n>`
   Claude is expected to (a) modify files in the working tree and (b) append entries to `/tmp/deepwork_changes.json` describing each change. Claude must **not** commit or push — that's step 5's job.
5. **Commit & push** — runs as identity `deepwork-action[bot] <deepwork-action[bot]@users.noreply.github.com>`. Detects "no changes" by checking `git diff`, `git diff --cached`, AND untracked files; sets `changes_made` output accordingly. Pushes via a token-rewritten remote URL.
6. **Post inline review comments** — only runs if `changes_made == 'true'`. Executes `scripts/post-review-comments.py`, which reads `/tmp/deepwork_changes.json`, generates per-file comment bodies (with a diff-stats fallback if a file isn't in the JSON), and POSTs a single review with `event: COMMENT` and one comment per file.

## Self-trigger guard

The example workflow uses `if: github.actor != 'deepwork-action[bot]'` at the **job level** to prevent the auto-fix commit from re-triggering the workflow. This guard is the only thing keeping the action from looping. Any change to the bot identity in step 5 of `action.yml` must be matched in the example workflow's `if` condition and in any documentation that references the actor name.

## State files crossing process boundaries

Three pieces of state flow between independent processes — keep them in sync when modifying any one of them:

| File | Written by | Read by | Purpose |
|---|---|---|---|
| `/tmp/deepwork_changes.json` | Claude (per `prompts/review.txt`) | `scripts/post-review-comments.py` | Per-change descriptions for inline comments. Schema: `{"changes": [{"file", "line", "description", "reason"}]}`. The Python script is tolerant of missing/malformed entries and falls back to diff stats. |
| `.deepwork/tmp/` | DeepWork plugin (inside Claude Code) | GitHub Actions cache (next run) | Review pass/fail state per PR — enables incremental review across commits. |
| `/tmp/deepwork_review_payload.json` | `post-review-comments.py` | `gh api ... --input` | Transient; just the request body for the GitHub PR review API. |

If you change the JSON schema in `prompts/review.txt`, you must update `load_changes_by_file` and `build_comment_body` in `scripts/post-review-comments.py` to match. The prompt is the contract.

## Versioning the action

This action is consumed via `Unsupervisedcom/deepwork-action@v1`. When making a release, the `v1` tag must be moved to the new commit (standard GitHub Actions major-version-tag convention). The README and example workflow both pin `@v1`.

## Testing changes

There is no local test harness. To validate changes end-to-end you must push a branch and open a PR in a repo that consumes this action (pinning the action to your branch via `Unsupervisedcom/deepwork-action@<branch>`). The Python script can be smoke-tested locally by setting `PR_NUMBER`, `GITHUB_REPOSITORY`, `GITHUB_BASE_REF` and running it inside a real git checkout, but it will only succeed in posting comments if `gh` is authenticated against a real PR.
