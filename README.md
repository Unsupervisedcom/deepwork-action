# deepwork-action

A prebuilt GitHub Action that runs [Claude Code](https://docs.anthropic.com/en/docs/claude-code) on a Pull Request with the [DeepWork](https://github.com/Unsupervisedcom/deepwork) plugin installed, triggers the `/review` skill, auto-commits every review-driven improvement back to the PR branch, and posts inline PR review comments explaining each change.

## How It Works

1. **Cache restore** — Restores the DeepWork plugin's per-PR review state from GitHub Actions cache so already-passed reviews are not re-run on subsequent commits.
2. **DeepWork review via Claude Code Action** — Invokes [`anthropics/claude-code-action@v1`](https://github.com/anthropics/claude-code-action) with `plugins: deepwork@deepwork-plugins` and `plugin_marketplaces: https://github.com/Unsupervisedcom/deepwork.git`, then runs the `/review` skill against the PR. The skill reads your `.deepreview` config files, dispatches parallel review agents scoped to exactly the right files, and applies every finding.
3. **Commit & push** — Claude commits and pushes its file edits to the PR branch using the git tools the upstream action pre-allows. Commits are authored as `deepwork-action[bot]`.
4. **Tracking comment** — `track_progress: true` produces a single live progress comment on the PR with checklisted phases (gather → review → apply → re-run → summary) and a per-rule findings summary including the commit SHAs the fixes landed in. This is the action's only output surface — there are no per-line inline comments (the upstream `claude-code-action@v1` system prompt explicitly forbids creating new comments on `pull_request` events; everything goes through the tracking comment).

## Prerequisites

1. **Anthropic API key** — add it as a repository secret named `ANTHROPIC_API_KEY`.
2. **`.deepreview` configuration** — place one or more `.deepreview` files in your repository defining your review rules. See the [DeepWork Reviews documentation](https://github.com/Unsupervisedcom/deepwork/blob/main/README_REVIEWS.md) for details.

## Usage

Create a workflow file such as `.github/workflows/deepwork-review.yml` (a copy of [`examples/deepwork-review.yml`](examples/deepwork-review.yml) in this repo):

```yaml
name: DeepWork Review

on:
  pull_request:
    types: [opened, synchronize]

concurrency:
  group: deepwork-review-${{ github.event.pull_request.number }}
  cancel-in-progress: true

jobs:
  deepwork-review:
    runs-on: ubuntu-latest
    permissions:
      contents: write       # push auto-fix commits to the PR branch
      pull-requests: write  # post inline PR review comments and progress tracker
      id-token: write       # OIDC for anthropics/claude-code-action

    steps:
      - name: Checkout PR branch
        uses: actions/checkout@v4
        with:
          fetch-depth: 1
          ref: ${{ github.event.pull_request.head.ref }}
          token: ${{ secrets.GITHUB_TOKEN }}

      - name: Run DeepWork Review
        uses: Unsupervisedcom/deepwork-action@v1
        with:
          anthropic_api_key: ${{ secrets.ANTHROPIC_API_KEY }}
          github_token: ${{ secrets.GITHUB_TOKEN }}
```

No self-trigger guard is needed: commits pushed by the action via `GITHUB_TOKEN` do not re-trigger `pull_request` workflow runs (GitHub's built-in rule).

## Inputs

| Input | Required | Default | Description |
|-------|----------|---------|-------------|
| `anthropic_api_key` | ✅ | — | Anthropic API key for Claude Code |
| `github_token` | ✅ | — | GitHub token with `contents: write` and `pull-requests: write` |
| `model` | ❌ | `claude-opus-4-6` | Claude model to use |
| `max_turns` | ❌ | `100` | Maximum agentic turns for Claude Code |
| `commit_message` | ❌ | `chore: apply DeepWork review suggestions` | Commit message for auto-committed changes |

## What Gets Changed

The action applies **all** suggestions from your `.deepreview` rules, including:

- Bug fixes and null-safety checks
- Style and formatting improvements
- Performance optimisations
- Security hardening
- Documentation updates
- Refactoring suggestions

If no `.deepreview` rules are configured in the repository, the action exits cleanly without making any changes or commits.

## Review Comments

The action posts a **single live tracking comment** on the PR (via `track_progress: true`) showing the review's progress through each phase and a structured per-rule findings summary at the end. The summary lists which findings were applied vs. skipped, with the commit SHAs the fixes landed in, so your team can review the resulting commits in the **Files Changed** tab and accept, request modifications, or revert individual changes as needed.

There are no per-line inline review comments. The upstream `anthropics/claude-code-action@v1` system prompt explicitly forbids creating new comments on `pull_request` events for safety; all output flows through the tracking comment instead.

## Caching

Review state is cached per PR in `.deepwork/tmp` using GitHub Actions cache, keyed on the PR number. Already-passed reviews are not re-run when you push new commits to the same PR — only code that has changed since the last review is re-evaluated. **This is a major token cost saver.**

## Security

- Claude Code runs via the official [`anthropics/claude-code-action@v1`](https://github.com/anthropics/claude-code-action).
- Auto-fix commits are pushed under the `deepwork-action[bot]` identity. Since those commits are pushed with `GITHUB_TOKEN`, they do not re-trigger the workflow (GitHub's built-in rule).
- The action runs in a sandboxed GitHub Actions runner with only the secrets you explicitly pass through.

## License

See [LICENSE](LICENSE).
