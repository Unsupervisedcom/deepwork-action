# deepwork-action

A prebuilt GitHub Action that runs [Claude Code](https://docs.anthropic.com/en/docs/claude-code) on a Pull Request with the [DeepWork](https://github.com/Unsupervisedcom/deepwork) plugin installed, triggers the `/review` skill, auto-commits all review-driven improvements back to the PR branch, and posts inline PR review comments explaining each change.

## How It Works

1. **DeepWork plugin install** — The action installs the DeepWork plugin from the marketplace using Claude Code's native plugin system, loading all review skills, hooks, and MCP server configuration automatically.
2. **DeepWork review** — Claude Code runs the `/review` skill, which reads your `.deepreview` config files to discover review rules, diffs the PR branch, and dispatches parallel review agents scoped to exactly the right files.
3. **Apply changes** — Claude applies every suggested improvement (bugs, style, performance, security, docs, refactoring) without asking for confirmation.
4. **Auto-commit** — All file changes are committed back to the PR branch under the `deepwork-action[bot]` identity.
5. **Inline PR comments** — A GitHub PR review is posted with one inline comment per changed file, describing what was changed and why, so your team can review each improvement.

## Prerequisites

1. **Anthropic API key** — add it as a repository secret named `ANTHROPIC_API_KEY`.
2. **`.deepreview` configuration** — place one or more `.deepreview` files in your repository defining your review rules. See the [DeepWork Reviews documentation](https://github.com/Unsupervisedcom/deepwork/blob/main/README_REVIEWS.md) for details.

## Usage

Create a workflow file such as `.github/workflows/deepwork-review.yml`:

```yaml
name: DeepWork Review

on:
  pull_request:
    types: [opened, synchronize, reopened]

concurrency:
  group: deepwork-review-${{ github.event.pull_request.number }}
  cancel-in-progress: true

jobs:
  deepwork-review:
    runs-on: ubuntu-latest
    # Don't re-run on commits pushed by the action itself
    if: github.actor != 'deepwork-action[bot]'
    permissions:
      contents: write       # push auto-fix commits to the PR branch
      pull-requests: write  # post inline PR review comments

    steps:
      - name: Checkout PR branch
        uses: actions/checkout@v4
        with:
          fetch-depth: 0
          ref: ${{ github.event.pull_request.head.ref }}
          token: ${{ secrets.GITHUB_TOKEN }}

      - name: Run DeepWork Review
        uses: Unsupervisedcom/deepwork-action@v1
        with:
          anthropic_api_key: ${{ secrets.ANTHROPIC_API_KEY }}
          github_token: ${{ secrets.GITHUB_TOKEN }}
```

## Inputs

| Input | Required | Default | Description |
|-------|----------|---------|-------------|
| `anthropic_api_key` | ✅ | — | Anthropic API key for Claude Code |
| `github_token` | ✅ | — | GitHub token with `contents: write` and `pull-requests: write` |
| `model` | ❌ | `claude-opus-4-6` | Claude model to use |
| `max_turns` | ❌ | `50` | Maximum agentic turns for Claude Code |
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

After pushing the auto-fix commit, the action posts a GitHub PR review with inline comments on each changed file. The comments appear in the **Files Changed** tab and describe what was changed and why, so your team can accept, request modifications, or revert individual changes as needed.

## Caching

Review state is cached per PR using GitHub Actions cache, keyed on the PR number. This means already-passed reviews are not re-run when you push new commits to the same PR — only code that has changed since the last review is re-evaluated. THIS IS A MAJOR TOKEN COST SAVER!!!

## Security

- Claude Code is installed and run via the official [`anthropics/claude-code-base-action`](https://github.com/anthropics/claude-code-base-action).
- The action runs with `--dangerously-skip-permissions` in a sandboxed GitHub Actions runner. It has no access to secrets beyond what you explicitly provide.
- Auto-fix commits are pushed under the `deepwork-action[bot]` identity. The example workflow includes `if: github.actor != 'deepwork-action[bot]'` at the job level so the action never triggers itself recursively.

## License

See [LICENSE](LICENSE).
