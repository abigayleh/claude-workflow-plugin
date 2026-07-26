# Verification conventions

The governing rule: **report exactly what ran.** Never say "tests pass" when no
test runner exists, and never let lint and build stand in for behavioral
evidence they can't provide.

## Find out what the project actually has

Don't assume. Run:

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/detect-stack.py"
```

It returns the real `test`, `lint`, `build`, `typecheck`, and `dev` commands
for the repo, or `null` where none exists. `has_test_runner: false` means there
is nothing to run — say that plainly instead of substituting something weaker
and calling it verification.

## What each check actually proves

| Check | Proves | Does not prove |
|---|---|---|
| Lint | Style and some classes of error | Anything runs |
| Typecheck | Types are internally consistent | Runtime behavior |
| Build | Imports and references resolve | Behavior is correct |
| Unit tests | The tested behavior holds | Untested paths hold |
| User's manual check | The flow works for a human | Edge cases |

The build is usually the strongest automated gate in a project without tests —
it catches broken imports and dangling references that a linter misses. It
still says nothing about whether the feature does the right thing.

## When there is no test runner

This is common in side projects and early-stage work. Handle it honestly:

1. Run whatever does exist (lint, typecheck, build, syntax check) and name each
   one in the report.
2. State the gap in one line: *"No test runner in this repo — lint and build
   passed, which confirms nothing is referentially broken but not that behavior
   is correct."*
3. Treat the user's manual check as the real evidence. The `dev-verify` skill
   exists for exactly this handoff.

Do not offer to add a test framework mid-task unless asked. Note it as a
recommendation and move on.

## When there is a test runner

- Run the full suite, not just the file you touched — the point is catching
  what you didn't think about.
- A pre-existing failure is not yours to hide. Record the baseline before
  changing anything so you can tell "I broke this" from "this was already red".
- **Never weaken, skip, or delete a test to make it pass.** A failing test is
  information. If a test genuinely looks wrong, say so and let the user decide.

## Writing tests

Tests are written from the spec, not from the implementation. A test derived by
reading the code asserts what the code does — including its bugs — rather than
what it should do. See the `test-writer` agent, which is deliberately denied
Bash and kept away from source files for this reason.

Cover: happy path, boundaries, invalid input, error handling, and the edge
cases implied by the spec.
