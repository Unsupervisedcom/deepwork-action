# Python Conventions

Conventions for Python code in this repository. Keep this short and
actionable — it's a reference for reviewers, not an exhaustive style
guide. (Originally derived from `scripts/post-review-comments.py`, which
has since been deleted. The conventions remain valid for any future Python
files added to the repo.)

## Module structure

- Start with `#!/usr/bin/env python3` shebang for executable scripts.
- Module-level docstring (triple-quoted) immediately after the shebang,
  describing what the script does, what it reads, what it writes, and how
  it's invoked. Multi-line is fine.
- `from __future__ import annotations` near the top so type hints don't
  evaluate at runtime.
- Imports: stdlib only when possible (this repo runs in CI with no extra
  pip installs). Order: `__future__` → stdlib → third-party → local.
- Use `# ---------------------------------------------------------------------------`
  banners with a `# Section Title` line to separate logical sections inside
  a single-file script. This makes a flat script readable without splitting
  it into modules.

## Naming and types

- `snake_case` for functions and variables; `PascalCase` for classes (none
  in current code).
- Type-hint every function signature, including return types. Use the
  built-in generic syntax (`list[str]`, `dict[str, Any]`) — not the
  `typing.List` / `typing.Dict` legacy aliases. `from __future__ import
  annotations` makes this work on older Pythons.
- Use `Any` (`from typing import Any`) sparingly — only when the structure
  is genuinely dynamic (e.g., a JSON-decoded payload).

## Functions and structure

- Prefer small, named top-level functions over inline blocks. Each
  logical step should be its own function.
- Keep `main()` as the orchestration entry point. Wire it via
  `if __name__ == "__main__": main()`.
- Don't introduce dataclasses or classes unless there's actual state to
  hold. The script-style this repo uses is dict-based.

## I/O and external commands

- For shell commands, use `subprocess.run(cmd, capture_output=True, text=True)`
  via a small `run()` wrapper rather than `os.system` or `subprocess.call`.
- Read paths via `pathlib.Path`, not `open(string)`.
- Read environment variables with `os.environ.get("NAME", default)` — never
  raw `os.environ["NAME"]` for inputs that might be missing.
- For non-fatal failures, print a warning to `sys.stderr` and
  `sys.exit(0)` so the calling CI step doesn't fail. Hard-fail with
  `sys.exit(1)` only for actual broken state.

## Strings and formatting

- f-strings for interpolation. No `%` formatting, no `.format()`.
- Multi-line string concatenation with parentheses, not `+`.

## Error handling

- Catch specific exception classes, not bare `except:` or `except Exception:`.
  Keep exception lists narrow (e.g., `except (json.JSONDecodeError, OSError) as exc:`).
- Print warnings with the exception value: `print(f"Warning: ... {exc}",
  file=sys.stderr)`.

## Comments and docstrings

- Function docstrings are triple-quoted, one-line summaries unless the
  function does something subtle that justifies a multi-line docstring.
- Inline comments explain *why*, not *what*. Let function names carry the
  meaning; keep inline comments sparse.
- Section banners (`# ----` blocks) are the exception: they're structural,
  not explanatory.
