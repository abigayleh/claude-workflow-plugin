---
name: git-workflow
description: Worktree-per-change git flow — create a worktree and branch for a feature or bug, commit to it, rebase onto the base branch, push, and hand off a pull request. Use when starting any new feature or bug fix, and when finishing one. Covers worktree setup, branch naming, safe rebasing, conflict handling, and the PR handoff. Claude never merges to the base branch unless the repo opted out with .claude/allow-merge-to-base.
when_to_use: Starting a feature or bug fix; asked to branch, add a worktree, rebase, merge, or push; finishing a change that needs to reach a pull request or land on the base branch.
argument-hint: "[start <short-description> | finish]"
allowed-tools: Bash, Read
---

# Worktree → commit → rebase → push → PR

Full conventions: `${CLAUDE_PLUGIN_ROOT}/conventions/git.md`. This skill is the
procedure.

**The boundary: you take work to ready-for-PR and stop.** You never commit to
the base branch, never push to it, and never merge into it. Three hooks enforce
this. If one blocks you, it is working correctly — don't route around it.

**Unless the repo opted out.** A repo with `.claude/allow-merge-to-base` in its
main checkout has said the pull request is ceremony it doesn't want — solo
project, no reviewer on the other side. There, finish by merging instead of
handing off. Check once, at the start:

```bash
test -f "$(git rev-parse --path-format=absolute --git-common-dir)/../.claude/allow-merge-to-base"
```

Pushing to the base is still blocked either way, so merged work stays local
until the user pushes it themselves. Say so when you hand back.

## Finding the base branch

Never assume `main`:

```bash
bash "${CLAUDE_PLUGIN_ROOT}/scripts/default-branch.sh"
```

- **exit 0** → the name is on stdout. Use it.
- **exit 3** → ambiguous; candidates printed. **Ask the user. Do not pick.** If
  a remote exists, the real fix is `git remote set-head origin -a`.
- **exit 1** → no branches yet; nothing to branch from.

## Starting work

Create the worktree as a sibling of the repo, then work inside it. Unlike
`git switch`, `git worktree add` does **not** touch the current folder — it
never changes the user's branch and is safe even with a dirty tree, because the
new worktree is checked out fresh from the base.

```bash
BASE=$(bash "${CLAUDE_PLUGIN_ROOT}/scripts/default-branch.sh") || exit
git fetch origin --prune        # skip entirely if there is no remote
REPO=$(basename "$(git rev-parse --show-toplevel)")
# The folder name flattens the branch's "/" to "-" so it stays one sibling dir.
git worktree add "../$REPO-feat-short-description" -b feat/short-description "origin/$BASE"
cd "../$REPO-feat-short-description"   # use "$BASE" not "origin/$BASE" if no remote
```

Do every later step from inside this folder.

Because the worktree starts from the base, **uncommitted work in the user's main
folder stays behind.** If they meant that work to be part of this change, stop
and ask before proceeding.

### Branch names

`type/kebab-case-description` — 2–5 words, lowercase and hyphens. Use `feat/`,
not `feature/`, matching the commit types.

`feat/add-password-reset` · `fix/null-user-response` ·
`refactor/extract-fetch-logic` · `chore/bump-prisma`

## Committing

Follow the `commit-message` skill: one line, `type: summary`, no body. A hook
rejects anything else.

## Rebasing onto the base

**First, check the branch isn't shared.** Rebasing rewrites hashes; if anyone
has pulled these commits, their next pull produces duplicate, conflicting
history. Treat as shared if either succeeds:

```bash
git rev-parse --abbrev-ref 'HEAD@{upstream}' 2>/dev/null   # has upstream => pushed
git branch -r --contains HEAD                              # non-empty => published
```

Shared → **stop and ask.** Do not rebase autonomously.

Otherwise:

```bash
git fetch origin --prune        # skip if no remote
git rebase "origin/$BASE"       # or "$BASE" if no remote
```

Don't use `--autostash`: it hides dirty state you should handle deliberately,
and reapplying it can conflict.

### On conflict

Rebase exits 1 and leaves `.git/rebase-merge/`. List what conflicted:

```bash
git diff --name-only --diff-filter=U
```

**Default action: `git rebase --abort`, then report the conflicting files to
the user.** That restores the branch and a clean tree exactly.

- **Never** `git rebase --skip` — it silently discards a commit.
- Resolve without asking only when the conflict is unambiguous *and* the result
  can be validated by the project's checks. Anything else is the user's call.

## Pushing

Preconditions — check all of them, and if one fails, say which and stop:

1. `git status --porcelain` is empty
2. Not detached: `git symbolic-ref -q HEAD` succeeds
3. No rebase in progress: no `.git/rebase-merge/` or `.git/rebase-apply/`
4. Base freshly fetched, and the branch rebased onto it
5. Verification passed — see `${CLAUDE_PLUGIN_ROOT}/conventions/testing.md`

```bash
git push -u origin feat/short-description            # first push
git push --force-with-lease --force-if-includes      # after a rebase
```

Never bare `--force`: it overwrites teammates' commits unconditionally.
`--force-with-lease` alone is fooled by a bare `git fetch`, which updates the
tracking ref without integrating — `--force-if-includes` covers that.

No remote? Skip the push, say so, and report the branch name instead.

## Finishing: merge, in an opted-out repo

Only when the marker above is present. Rebase onto the *current* base first —
it moves — then confirm the main checkout is where you think it is, in one
command, and abort unless it is:

```bash
git -C ../<repo> branch --show-current && git -C ../<repo> rev-parse HEAD
git -C ../<repo> merge --ff-only feat/short-description
```

`--ff-only` refuses if the base moved again: rebase again and retry rather than
forcing it. Then clean up after yourself — the merge keeps every commit, so
removing the worktree only discards the folder:

```bash
git worktree remove ../<repo>-feat-short-description
git branch -d feat/short-description      # -d, never -D
```

## Handing off the pull request

**Everywhere else, this is where you stop.** Report what landed on the branch
and give the user the command:

```bash
gh pr create --base <base> --head <branch> --title "type: summary" --body "..."
```

Include in your report: the branch, the base, the files changed, what
verification actually ran, and what the reviewers said. For anything visual,
add a `dev-verify` checklist.

Leave the worktree in place — the user may want to look at it. If they confirm
the PR is merged and ask you to clean up:

```bash
git worktree remove ../<repo>-feat-short-description
git branch -d feat/short-description      # -d, never -D
```

`-d` refuses to delete a branch whose commits aren't reachable from the base, so
a refusal is real information: the merge didn't land what you thought. `-D`
deletes unconditionally and discards the commits.
