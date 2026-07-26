# Git conventions

## The rule that shapes everything else

**Claude never lands work on the base branch.** It builds on a feature branch
in its own worktree, verifies, pushes, and stops at ready-for-PR. The user
opens the pull request and merges it.

Three hooks enforce this rather than trusting it: commits to the base branch
are blocked, pushes to the base are blocked, and merges into the base are
blocked. See `hooks/`.

## Worktrees, not branch switching

Every change gets its own branch **in its own worktree** — a separate folder on
disk. `git switch` in a shared checkout changes the branch under whoever else
is working there; `git worktree add` never does, and is safe even with a dirty
tree.

```bash
git worktree add "../$REPO-feat-short-description" -b feat/short-description "$BASE"
```

One worktree per task. Parallel work gets one folder each so two agents can't
collide on a shared `HEAD`.

## Branch names

`type/kebab-case-description` — same types as commits, 2–5 words, lowercase and
hyphens only. Use `feat/`, not `feature/`, so branch and commit vocabularies
match.

`feat/add-password-reset` · `fix/null-user-response` ·
`refactor/extract-fetch-logic` · `chore/bump-prisma`

## Commits

**A single line. `type: summary`. No body, ever.**

```bash
git commit -m "feat: add password reset flow"
```

Types: `build` `chore` `ci` `docs` `feat` `fix` `perf` `refactor` `revert`
`style` `test`. Summary in imperative mood, lowercase, no trailing period, ~50
characters and never past 72. Optional scope: `fix(parser): handle empty
input`. Breaking change: `feat(api)!: drop v1 endpoints`.

Why no body: a body is where a change that couldn't be summarized goes to hide.
If one line won't cover it, the commit is doing too much — split it. The commit
hook rejects bodies, multiple `-m` flags, messages from files or heredocs, and
missing type prefixes.

No AI attribution or co-author footers.

## Rebasing

**Check the branch isn't shared first.** Rebasing rewrites hashes; if anyone has
pulled these commits, their next pull produces duplicate history. Treat as
shared if either command succeeds:

```bash
git rev-parse --abbrev-ref 'HEAD@{upstream}'   # has an upstream => pushed
git branch -r --contains HEAD                  # non-empty => published
```

If shared, stop and ask.

Don't use `--autostash` — it hides dirty state you should handle deliberately,
and reapplying it can conflict. Commit or stash explicitly.

**On conflict, the default is `git rebase --abort`** and report the conflicting
files. Never `git rebase --skip`; it silently discards a commit. Resolve
without asking only when the conflict is unambiguous *and* the result can be
validated by the project's checks.

## Pushing

Feature branches only. After a rebase the push is non-fast-forward, so it needs
the safe force:

```bash
git push --force-with-lease --force-if-includes
```

Never bare `--force` — it overwrites teammates' commits unconditionally.
`--force-with-lease` alone is fooled by a bare `git fetch`, which updates the
tracking ref without integrating; `--force-if-includes` covers that.

## Never assume the base branch is `main`

Run `scripts/default-branch.sh`. Exit 0 gives the name; exit 3 means genuinely
ambiguous — **ask the user, don't pick**; exit 1 means no branches yet.
