---
name: fix-bug
description: Fix a specific bug — diagnose the root cause, apply the fix, confirm the bug is actually gone, quality check, push, then hand off a PR. Lighter than ship-feature (no test-writer, no parallel stages, no ui-checker unless the bug is visual).
when_to_use: A specific, already-identified bug needs fixing — an error message, a failing test, a reproducible misbehavior.
argument-hint: "[bug description, error message, or failing test name]"
---

# Fix a bug

You're fixing the specific bug described in this skill's arguments.

Smaller than `ship-feature` — no parallel stages, no test-writer. **Ends at a
pull request the user opens; you never merge to the base branch.**

## Step 0 — worktree

Follow `git-workflow` to create a `fix/...` branch in its own worktree off the
base branch.

## Step 1 — detect the stack

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/detect-stack.py"
```

Use the commands it reports. If `ecosystem` is `unknown`, ask the user.

## Step 2 — diagnose

Launch the `debugger` subagent with the bug description. It reproduces the
issue and reports a root cause plus a recommended fix. It does not edit code.

**If it says it couldn't reproduce the bug, stop and report that.** Don't have
`code-writer` implement a fix for a cause nobody confirmed — you'd be changing
working code on a guess and calling the bug fixed.

## Step 3 — fix

Launch `code-writer` with the debugger's root-cause report. It implements the
recommended fix, touches nothing unrelated, and **must not weaken or delete any
test to make it pass**.

## Step 4 — confirm

Two separate things, and the second is the one that matters:

1. **The project's checks** — run whatever Step 1 found (`test`, `lint`,
   `typecheck`, `build`). Report exactly what ran; skip and name what's absent.
2. **The actual bug** — reproduce it the way the debugger did in Step 2 and
   confirm it's gone. Lint and build don't know what the bug was.

If the bug had a visual symptom, use `dev-verify` to hand the user a checklist
confirming the fix, and wait for their answer.

## Step 5 — quality check

Launch `code-quality-reviewer` on the diff. If the bug was visual, also launch
`ui-checker` on the same diff — otherwise skip it.

A bug fix deserves one extra question: **is this the root cause or the symptom?**
A fix that adds a null check where the null shouldn't have existed will pass
every check here and leave the real bug in place.

## Step 6 — decide

**Fixed, and no blocking review feedback:**

1. `diff-review` the working diff.
2. Commit per `commit-message` — `fix: ...`, one line.
3. Rebase onto the current base per `git-workflow`, then push the branch.
4. Report and stop: root cause, what changed, what verification ran, and the
   `gh pr create` command. **The user opens the PR.**

**Still wrong:** return to Step 2 with the new failure information, up to 2
total attempts. After that, stop and report the current state rather than
retrying — this needs a human look. Leave the work on the branch.
