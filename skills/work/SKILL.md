---
name: work
description: Run the full idea-to-shipped-code pipeline for a new feature or fix — grill requirements, brainstorm/design, write tests first, implement, iterate until green, then a thermo-nuclear code quality review. Use when the user wants to "just build" something end-to-end rather than run each step by hand, or explicitly invokes /work.
---

# Work

Chains five existing skills into one fixed pipeline. Each step's own hard gates (approvals, STOP conditions) still apply in full — this skill sequences them, it does not skip or soften them.

## Pipeline

1. **Grill** — Skill(`mattpocock-skills:grilling`). Interview the user until the design tree is settled: what's being built, for whom, the constraints. Do this first, even if the request already looks simple.
2. **Brainstorm** — Skill(`brainstorming`). Hand it what the grill settled. Let it classify the work itself (spike / bounded / architectural) and run its own approval gate — the grill answering "what" doesn't satisfy brainstorming's separate "present design, get approval" step; that still has to happen.
   - If brainstorming escalates to **architectural** and calls for the `writing-plans` skill, that skill isn't installed here. Stop and tell the user rather than inventing a plan-document format or skipping the step.
3. **Tests first** — Skill(`mattpocock-skills:tdd`). Only once the design is approved: write the failing tests for it before any implementation code (the red half of the TDD loop).
4. **Implement** — Skill(`mattpocock-skills:implement`), against the approved design and the tests just written. It will itself lean on TDD at pre-agreed seams — expected, not a deviation.
5. **Iterate to green** — keep implementing/fixing and rerunning the suite until every test this pipeline wrote passes, plus a typecheck if the project has one. Don't advance to step 6 on a red suite.
6. **Review** — with tests green, run Skill(`thermo-nuclear-code-quality-review`). This replaces `implement`'s own suggested `/code-review` step — this pipeline's review is the strict one.

## Notes

- Run the steps in order. Don't reorder or skip one because the request "looks simple" — that call belongs to the grill/brainstorm steps themselves, not to this wrapper.
- If any step's own gate isn't met (e.g. brainstorming's bounded/architectural approval), stop there and wait. This skill grants no blanket authorization to bypass a downstream skill's gate.
- Branching/committing follows whatever this repo's own git conventions are (see the `git-workflow` skill where installed) — `work` doesn't add its own branch or commit handling on top.
