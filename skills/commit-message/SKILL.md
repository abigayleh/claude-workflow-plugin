---
name: commit-message
description: Use when making a git commit — when to commit, and the required single-line message format. Enforced by a PreToolUse hook that rejects bodies, multiple -m flags, and missing type prefixes.
when_to_use: About to run git commit; asked to write or fix a commit message.
allowed-tools: Bash
---

# Commit conventions

Full rules: `${CLAUDE_PLUGIN_ROOT}/conventions/git.md`.

## When to commit

- After a logically complete change that has passed the `diff-review` skill.
- One commit per coherent change — don't bundle unrelated work.
- Never commit broken or half-finished code.
- Always to a feature branch, never the base. A hook blocks the latter.

## Format

**A single line. `type: summary`. No body, ever.**

```bash
git commit -m "feat: add password reset flow"
```

- **Types**: `build` `chore` `ci` `docs` `feat` `fix` `perf` `refactor`
  `revert` `style` `test`
- **Summary**: imperative mood, lowercase, no trailing period. Aim for ~50
  characters, hard ceiling 72.
- Optional scope: `fix(parser): handle empty input`. Breaking change marked with
  `!` before the colon: `feat(api)!: drop v1 endpoints`.
- **No body, no bullets, no AI attribution or co-author footers.**

**Why no body:** a body is where a change that couldn't be summarized goes to
hide. If one line won't cover it, the commit is doing too much — split it.

## Examples

- `feat: add password reset flow`
- `fix: handle null response from user endpoint`
- `refactor: extract shared fetch logic`
- `chore: bump prisma to 5.14`

## Enforcement

`hooks/check-commit-msg.py` blocks any `git commit` that carries a body, uses
multiple `-m` flags, sources the message from a file or heredoc, omits `-m`, or
lacks a valid type prefix — and any commit that targets the base branch.

If it rejects a commit, fix the message. Don't work around the hook.
