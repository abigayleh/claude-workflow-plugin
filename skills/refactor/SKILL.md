---
name: refactor
description: Restructure existing code without changing behavior — baseline first, apply the refactor, confirm nothing broke via the project's checks plus a user-driven behavioral check, quality review, push, then hand off a PR.
when_to_use: Asked to restructure, extract, consolidate, tidy, or clean up existing code where behavior is supposed to stay identical.
argument-hint: "[what to refactor and why]"
---

# Refactor

You're restructuring the code described in this skill's arguments.

Conventions: `${CLAUDE_PLUGIN_ROOT}/conventions/refactoring.md`.

**The defining constraint: behavior must not change.** Only structure,
readability, and duplication should.

## Step 0 — worktree

Follow `git-workflow` to create a `refactor/...` branch in its own worktree.

## Step 1 — baseline, and name the risk

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/detect-stack.py"
```

**Run the project's checks before touching anything** and record the result, so
you can tell "I broke this" from "this was already failing".

Then two things, in one line each:

1. **Name what could silently change** that no automated check here would catch.
   If you can't name it, you don't understand the code well enough to refactor
   it yet — read more first.
2. **If `has_test_runner` is false, say so explicitly to the user before
   starting.** A refactor normally leans on tests to prove behavior didn't
   change. Without them that proof doesn't exist, lint and build only catch
   broken references, and you cannot close the gap by being careful. Step 4 is
   the real safety net.

## Step 2 — refactor

Launch `code-writer` with the goal. It should:

- change structure, not behavior — no new features, no bug fixes bundled in
- stay scoped to what was asked, not a drive-by cleanup of everything nearby
- preserve the public shape of what it touches — same inputs, outputs, side
  effects

If it finds a real bug along the way, it flags it rather than fixing it. A fix
hidden inside a "behavior-preserving" change is a fix nobody reviewed.

## Step 3 — confirm nothing broke

Re-run the Step 1 checks and compare to the baseline. Anything clean before must
be clean now.

Be honest about what this proves: with tests, a good deal. Without them, only
that nothing is *referentially* broken. It is not evidence behavior is unchanged.

## Step 4 — confirm behavior with the user

In a repo without tests, this is the real safety net — not Step 3.

Use `dev-verify` to start the app and hand the user a checklist covering the
flows that run through the refactored code, **including the ones that merely
touch it** — a refactor's risk lives in the callers you didn't think about.
Wait for their answer.

If the code has no user-facing surface at all, say so, and state plainly that
this refactor is going in without behavioral verification.

## Step 5 — quality check

Launch `code-quality-reviewer` on the diff, focused on whether the refactor
actually improved things — duplication, clarity, naming — rather than just
moving code around. If it touched markup, styles, or layout, also launch
`ui-checker`.

## Step 6 — decide

**Checks clean, user confirmed behavior unchanged, no blocking feedback:**

1. `diff-review` the working diff.
2. Commit per `commit-message` — `refactor: ...`, one line.
3. Rebase onto the current base per `git-workflow`, then push the branch.
4. Report and stop: what was restructured, why, what verification actually ran,
   and the `gh pr create` command. **The user opens the PR.**

**Something broke:** launch `debugger` on the specific failure to find what the
refactor broke, have `code-writer` correct it, re-run Step 3. Cap at 2 attempts
— if it's still broken after that, stop and report rather than keep iterating on
what was supposed to be a behavior-preserving change. Consider that the
right move may be to abandon the branch.
