# deepwork-action

A prebuilt GitHub Action that runs [Claude Code](https://docs.anthropic.com/en/docs/claude-code) on a Pull Request with the [DeepWork](https://github.com/Unsupervisedcom/deepwork) plugin installed, triggers the `/review` skill, auto-commits all review-driven improvements back to the PR branch, and posts inline PR review comments explaining each change.

## How It Works

1. **DeepWork review** — Claude Code runs the `/review` skill, which reads your `.deepreview` config files to discover review rules, diffs the PR branch, and dispatches parallel review agents scoped to exactly the right files.
2. **Apply changes** — Claude applies every suggested improvement (bugs, style, performance, security, docs, refactoring) without asking for confirmation.
3. **Auto-commit** — All file changes are committed back to the PR branch under the `deepwork-action[bot]` identity.
4. **Inline PR comments** — A GitHub PR review is posted with one inline comment per changed file, describing what was changed and why, so your team can review each improvement.

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
| `model` | ❌ | `claude-sonnet-4-5` | Claude model to use |
| `max_turns` | ❌ | `50` | Maximum agentic turns for Claude Code |
| `commit_message` | ❌ | `chore: apply DeepWork review suggestions [skip ci]` | Commit message for auto-committed changes |

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

## Security

- The action runs Claude with `--dangerously-skip-permissions` in a sandboxed GitHub Actions runner. It has no access to secrets beyond what you explicitly provide.
- Auto-fix commits are signed with the `deepwork-action[bot]` identity.
- The `[skip ci]` suffix on the default commit message prevents the action from triggering itself recursively.

## License

See [LICENSE](LICENSE).
