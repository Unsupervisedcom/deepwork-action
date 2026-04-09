# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this repo is

A **composite GitHub Action** (not a JS/TS/Docker action) that delegates most of the heavy lifting to [`anthropics/claude-code-action@v1`](https://github.com/anthropics/claude-code-action). It installs the DeepWork plugin, runs `/review` against the PR, applies every finding as real file edits, and uses the upstream action's native machinery to auto-commit changes and post inline PR comments. There is no build system, no package manager, no test suite. The action is defined by `action.yml` and a single prompt file.

## Repository layout

- `action.yml` — the composite action definition. Three composite steps: cache restore, load the prompt file into a step output, invoke `anthropics/claude-code-action@v1`.
- `prompts/review.txt` — the prompt fed to Claude. Starts with `/review` to trigger the DeepWork plugin's review skill, then enforces CI-mode rules (no `AskUserQuestion`, apply every finding, iterate until clean, post inline comments via `mcp__github_inline_comment__create_inline_comment`).
- `examples/deepwork-review.yml` — reference workflow showing how downstream repos consume this action (pins `Unsupervisedcom/deepwork-action@v1`). Lives outside `.github/workflows/` so GitHub doesn't auto-execute it — it's documentation, not CI.
- `.github/workflows/self-review.yml` — this repo's own CI. Runs the action against its own PRs using `uses: ./` so the PR branch's `action.yml` is exercised (not the published `v1` tag). Without this split, a PR that edits `action.yml` could never test the edit before it gets tagged.
- `.deepwork/` — DeepWork plugin's local state. Only `.deepwork/review/` is source; `.deepwork/tmp/` is the cache directory (gitignored) restored from GitHub Actions cache at runtime.
- `.deepreview` — this repo's own review rules, so the action dogfoods itself.

## End-to-end flow

The action is now thin. In order, `action.yml` runs:

1. **Restore DeepWork review cache** via `actions/cache@v4`. Path is `.deepwork/tmp`, keyed on PR number + run id. The DeepWork plugin uses this directory to remember which reviews have already passed on a PR, so subsequent commits skip re-running already-passed checks — the main token-cost saver.
2. **Load review prompt** into a step output. Reads `prompts/review.txt` via bash heredoc into `${{ steps.load_prompt.outputs.content }}`. This exists because `anthropics/claude-code-action` only has a `prompt` input (no `prompt_file`), so we have to inline the text via an output.
3. **Run DeepWork Review** — invokes `anthropics/claude-code-action@v1` with:
   - `plugin_marketplaces: https://github.com/Unsupervisedcom/deepwork.git`
   - `plugins: deepwork@deepwork-plugins`
   - `prompt:` the review.txt content plus a header with the repo and PR number
   - `claude_args: --model <model> --max-turns <n> --dangerously-skip-permissions`
   - `track_progress: true` → live "Claude Code is reviewing..." comment on the PR
   - `use_commit_signing: false` → Claude uses plain `git commit` / `git push` for auto-fixes
   - `bot_name: 'deepwork-action[bot]'`

The upstream `claude-code-action` then:
- Installs the DeepWork plugin from the marketplace URL (note: the plugin's slash commands install fine but the plugin's MCP server currently fails to connect inside the action's runner — see "Known issues" below).
- Spawns Claude Code, which runs `/review`, reads `.deepreview` rules, dispatches reviewers in parallel, applies findings as real file edits.
- Pre-allows a small set of git tools (`git add`, `git commit`, `git-push.sh`, `git rm`) so Claude can commit and push its own edits. **Claude commits and pushes itself; the action does NOT auto-commit.** This was a footgun in an earlier draft of this repo where `prompts/review.txt` told Claude to never run git commands — Claude obediently made edits and then never saved them. The upstream system prompt expects Claude to commit; our prompt now matches.
- Posts inline PR comments for each change via the native `mcp__github_inline_comment__create_inline_comment` MCP tool.

## What used to be here and isn't anymore

Before the rewrite to `claude-code-action@v1`, `action.yml` had seven composite steps: install uv, restore cache, fetch base branch, prepare review run (`rm -f /tmp/deepwork_changes.json`), run `claude-code-base-action@beta`, commit & push, and a custom `scripts/post-review-comments.py` that diffed the PR and posted inline comments. The old commit `bc66f07 "proper plugin install"` configured the base action with `plugin_marketplaces`/`plugins`/`claude_args` inputs that never existed on `claude-code-base-action` in any published release — the plugin never actually installed in CI, and Claude was running the built-in `/review` slash command on default Sonnet with default permissions. Switching to `anthropics/claude-code-action@v1` (which has real `plugins`/`plugin_marketplaces`/`claude_args` inputs) let us delete all of that. If you see any stale references to `/tmp/deepwork_changes.json`, the custom commit step, `scripts/post-review-comments.py`, or `claude-code-base-action` in docs or code, they are leftovers — delete them.

## Self-trigger guard

There isn't one, and there doesn't need to be. GitHub Actions' built-in rule: **events triggered by the default `GITHUB_TOKEN` do not create new workflow runs.** Since `claude-code-action` pushes auto-fix commits using the `GITHUB_TOKEN` we pass in, those pushes do not re-trigger the `pull_request` workflow. No `if: github.actor != '...'` guard required. The example workflow previously had one, but it was misconfigured (checked for `deepwork-action[bot]` when the actual actor for GITHUB_TOKEN pushes is `github-actions[bot]`) and unnecessary to begin with.

If you ever switch the push path to use a Personal Access Token or a GitHub App token instead of `GITHUB_TOKEN`, the re-trigger protection disappears and you will need an explicit guard matching whichever bot name those credentials resolve to.

## The prompt contract

`prompts/review.txt` is the production prompt that ships to Claude in CI. Treat it as a critical file — review it strictly whenever it changes. Its essential guarantees:

1. Claude runs `/review` (the DeepWork plugin's skill, not Claude Code's built-in).
2. CI mode rules: never `AskUserQuestion`, apply every finding autonomously (with a false-positive escape valve), iterate until clean or 2 cycles, emit "No review rules configured." and stop if no `.deepreview` rules exist.
3. **Claude MUST commit and push** its file edits itself, using the pre-allowed `git add`, `git commit`, and `/home/runner/work/_actions/anthropics/claude-code-action/v1/scripts/git-push.sh origin HEAD` commands. The wrapping action does not auto-commit. Each iteration cycle should produce its own commit; never amend or force-push.
4. The output surface is the **single tracking comment** managed by the upstream `claude-code-action` via `mcp__github_comment__update_claude_comment`. Claude must not create new PR comments or post free-form chat replies. The upstream action's system prompt explicitly forbids `Never create new comments. Only update the existing comment` — our prompt does not fight this.
5. When findings conflict, prefer correctness over style.

If you change the prompt, update the drift checks in `.deepreview`'s `update_action_surface_docs` rule and this CLAUDE.md section to match.

## Known issues

### DeepWork plugin MCP server fails to start inside `claude-code-action`

When `anthropics/claude-code-action@v1` installs the DeepWork plugin in the runner, the plugin install reports success (`✓ Successfully installed: deepwork@deepwork-plugins`) **but the plugin's MCP server fails to connect**. The Claude Code session init reports:

```json
"mcp_servers": [
  { "name": "plugin:deepwork:deepwork", "status": "failed" },
  { "name": "github_comment",           "status": "connected" },
  { "name": "github_ci",                "status": "connected" }
]
```

There is no error message printed near the failure — silent. The plugin's slash commands DO work because `/review` is implemented as a skill file (prompt-style, no MCP needed), so reviews still run, BUT the MCP-provided tools (`get_configured_reviews`, `get_named_schemas`, `start_workflow`, `mark_review_as_passed`, the DeepSchema validation tools, the workflow orchestration tools) are all unavailable in CI. The reviews running today are a **degraded form**: file-edit-based, no quality gates, no DeepSchema validation, no workflow state machine. They produce useful autofixes but skip the structural integrity guarantees the full DeepWork pipeline provides.

The same plugin works fine outside CI. Leading hypotheses (under investigation):

1. `claude-code-action`'s `pull_request` security path restores `.claude/`, `.mcp.json`, `.claude.json`, `CLAUDE.md`, etc. from `origin/main` before running Claude — this could be wiping plugin MCP registration that the install step put down.
2. `MCP_TIMEOUT` and `MCP_TOOL_TIMEOUT` env vars are set to empty strings in the runner env — empty values may be interpreted as zero rather than "use default".
3. The plugin's MCP server has a startup dependency (network, filesystem path, env var) that exists in interactive use but not in the runner sandbox.

If you can fix this upstream in DeepWork or in `claude-code-action`, do — it's the biggest functional gap in the action right now. Until then, the degraded MCP-less review still produces useful output and the tracking comment makes it visible.

### `pull_request` file restoration

Before each run, `claude-code-action` restores these files from `origin/main`: `.claude/`, `.mcp.json`, `.claude.json`, `.gitmodules`, `.ripgreprc`, `CLAUDE.md`, `CLAUDE.local.md`, `.husky`. This is a security feature against prompt injection from PR content (`PR head is untrusted` per the runner log). Practical consequences:

- A PR that *adds* `CLAUDE.md` will run with no `CLAUDE.md` present in the working tree (because `origin/main` has none). The PR's CLAUDE.md is only visible to Claude via direct file reads, not via the auto-loaded context.
- Shipping `.mcp.json` in the repo to wire up MCP servers is pointless — it gets overwritten on every run. Use the `mcp_config:` input on `claude-code-action` instead.
- If you ever add a per-repo Claude Code settings file to this repo's tree, it won't take effect during the action's runs.

## Versioning the action

This action is consumed via `Unsupervisedcom/deepwork-action@v1`. The `v1` tag is a **floating major-version tag** that always points at the latest commit on `main` — standard GitHub Actions convention (see `actions/checkout@v4`, etc.). Consumers pin `@v1` and expect it to track the freshest `1.x.y` automatically.

**This means every release (and currently every merge to main) requires force-moving `v1`**:

```bash
git tag -f v1 origin/main
git push origin v1 --force
```

The README and example workflow both pin `@v1`, so this is the contract consumers rely on — don't change them to pin a specific `1.x.y` without also updating this section.

Release automation is planned. Until it lands, the `v1` tag is moved manually on every merge to main. If you see `v1` lagging behind `main`, that's a bug — move it.

## Testing changes

There is no local test harness. This repo dogfoods itself via `.github/workflows/self-review.yml`, which runs the action against its own PRs using `uses: ./` so edits to `action.yml` are exercised from the PR branch (not the published `v1` tag). Any PR opened against this repo also runs the action on its own changes.

To validate changes from an *external* consumer's perspective (i.e., the `uses: Unsupervisedcom/deepwork-action@...` path), push a branch and open a PR in a downstream repo pinning to your branch via `Unsupervisedcom/deepwork-action@<branch>`.
