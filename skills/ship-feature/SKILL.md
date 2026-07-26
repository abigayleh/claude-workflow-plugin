---
name: ship-feature
description: Run the full spec-to-ready-for-PR pipeline for a feature — worktree, detect the stack, implement, verify, review, capped fix loop, push the branch, re-review against the rebased branch, then hand the user a gh pr create command. Claude never merges to the base branch.
when_to_use: Building a new feature from a spec or description and taking it all the way to ready-for-PR.
argument-hint: "[spec file path, or a short feature description]"
---

# Ship a feature to ready-for-PR

You are orchestrating a fixed pipeline for the feature described in this
skill's arguments (a spec file path, or a short description).

Follow the stages in order. Don't skip or reorder them. **The pipeline ends at
a pull request the user opens — you never merge to the base branch, and hooks
will block you if you try.**

## Stage 0 — worktree

Follow the `git-workflow` skill to create a `feat/...` branch in its own
worktree off the base branch. Every commit goes there.

## Stage 1 — detect the stack

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/detect-stack.py"
```

This returns the project's real `test`, `lint`, `build`, `typecheck`, and `dev`
commands, or `null` where none exists. **Use these throughout — never assume a
command that wasn't reported.** Read the `notes` array; it flags things like
multiple lockfiles and missing runners.

If `ecosystem` is `unknown`, ask the user for their commands before continuing.

## Stage 2 — implement

Launch the `code-writer` subagent with the spec.

**If `has_test_runner` is true**, launch `test-writer` in the same message so
they run in parallel — and give it **only the spec**, never `code-writer`'s
output. Their independence is the entire value; a test written against the
implementation just asserts the bugs back.

If `has_test_runner` is false, skip `test-writer` and note that this feature is
shipping without automated behavioral coverage.

## Stage 3 — verify

Run the commands Stage 1 actually found — `test`, then `lint`, `typecheck`,
`build`. Skip any that are `null` and say which you skipped and why.

**Report exactly what ran.** Never say "tests pass" when `has_test_runner` is
false. See `${CLAUDE_PLUGIN_ROOT}/conventions/testing.md`.

Capture the failure output if anything fails.

## Stage 4 — first review

In a single message, launch both:

- `code-quality-reviewer` on the diff from Stage 2
- `ui-checker` on the same diff — **skip if there's no UI change**

Wait for both before continuing.

## Stage 5 — decide

Issues are "found" if any of these hold:

- Stage 3 verification failed
- `code-quality-reviewer` returned "Changes requested" or "Blocking issues"
- `ui-checker` returned "Needs changes"

Issues → Stage 6. None → Stage 7.

## Stage 6 — capped fix loop (max 3 attempts)

Keep a counter starting at 1.

1. Launch `debugger` with the specific failure output — verification failures
   and/or blocking review findings. It diagnoses only.
2. Launch `code-writer` with the debugger's root-cause report to implement the
   recommended fix.
3. Return to Stage 3, then Stage 4.
4. If issues remain and the counter is under 3, increment and repeat.
5. **After 3 attempts, stop and report the current state.** Three failed
   attempts means the problem isn't what you think it is; a fourth won't fix it.
   Leave the work on the branch and hand it to a human.

## Stage 7 — commit and push the branch

1. Review the working diff with the `diff-review` skill.
2. Commit following `commit-message` — one line, `type: summary`, no body.
3. Rebase onto the current base per `git-workflow`.
4. Push the feature branch:
   ```bash
   git push -u origin <branch>          # first push
   git push --force-with-lease --force-if-includes   # after a rebase
   ```

If the repo has no remote, skip the push and say so — the rest of the pipeline
still applies.

## Stage 8 — second review, against the rebased branch

The Stage 4 review saw the code as written. This one sees it **as the pull
request will**: rebased onto the current base, with whatever landed there in
the meantime. That's a different question, and it's where integration problems
surface.

1. Re-run the Stage 3 verification commands against the rebased branch. Code
   that passed before a rebase can fail after one.
2. Launch `code-quality-reviewer` on the **full branch diff against the base**
   (`git diff <base>...HEAD`), not just the last commit — the PR reviewer will
   see all of it.
3. If anything blocking appears, return to Stage 6.

## Stage 9 — hand off the PR

**Stop here.** Opening the pull request is the user's decision.

Report:

- What was implemented
- What verification actually ran, and its result — name the commands
- What each reviewer said, in both passes
- How many fix attempts were needed
- Anything you deliberately left alone, and why
- The command to open the PR:

```bash
gh pr create --base <base> --head <branch> --title "<type: summary>" --body "..."
```

If the feature has a visual surface, also hand over a `dev-verify` checklist so
the user can look at it before opening the PR.
