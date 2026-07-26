---
name: diff-review
description: Use after any code change, before committing. Reviews the working diff for correctness, security (injection, secret and data leaks, auth gaps), and performance (N+1 queries, unbounded fetches).
when_to_use: Just finished a code change and about to commit; asked to check a diff for security or performance problems.
allowed-tools: Bash, Read, Grep, Glob
---

# Diff review

Run this against every diff before committing.

```bash
git diff --staged    # or: git diff
```

## Security

Work through `${CLAUDE_PLUGIN_ROOT}/conventions/security.md` — the full
checklist lives there so it can't drift between this skill and the
`code-quality-reviewer` agent. Headline items:

- Injection: SQL, HTML/XSS, command, path traversal
- Secrets or PII in logs, error messages, client bundles, or committed files
- Auth: new routes have the access control they should, and verify identity
  server-side rather than trusting a client-supplied id

## Correctness

- Logic errors, off-by-one, unhandled edge cases
- Error paths: empty input, null, network failure
- Does this break callers elsewhere? Grep for usages before deciding it doesn't.

## Performance

- N+1 queries; redundant loops or recomputation; needless re-renders
- Unbounded fetches — missing pagination or limits
- Memoization only where clearly warranted; don't over-apply

## Scope

- Files changed that shouldn't have been
- New dependencies — flag every one, with what it's for
- Debug leftovers: stray logging, commented-out code, hardcoded test values

## Reporting

- Flag issues with `file:line`.
- **If nothing is found, say so explicitly** — silence reads as "not checked".
- **Call out security issues even when you also fix them.** A silent patch means
  the user never learns the pattern was there.
