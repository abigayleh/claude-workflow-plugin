# Refactoring conventions

A refactor changes structure, never behavior. Same inputs → same outputs, same
side effects, same public API.

## Before touching anything

1. **Understand it.** Read the whole file and enough of its callers to know how
   each piece is used. Never delete or merge something whose usage you haven't
   confirmed.
2. **Record the baseline.** Run the project's checks *first* so you can tell
   "I broke this" from "this was already failing".
3. **Name the risk.** State in one line what this refactor could silently
   change that no automated check would catch. If you can't name it, you don't
   understand the code well enough to refactor it yet.

## Rules

- **Small, reviewable changes.** A series of clear edits beats one sweeping
  rewrite — the diff has to stay readable.
- **Don't reformat for its own sake.** Respect existing style and formatter
  config. Don't churn lines that didn't need to change.
- **Don't bundle in fixes.** If you find a real bug, flag it and ask — don't
  quietly repair it inside a "behavior-preserving" change where nobody will
  review it as a fix.
- **Ask before anything destructive or ambiguous**: large deletions, API-shape
  changes, removing an effect whose external side effect you couldn't trace, or
  merging code whose call sites you couldn't verify.

## What to improve

**Reuse over repetition.** Pull duplicated or near-duplicated logic into one
well-named function. Use utilities the project already has instead of
reinventing them.

**Clarity.**
- Remove dead code, unreachable branches, unused variables, imports, parameters.
- Flatten convoluted conditionals with early returns and guard clauses.
- Collapse needless intermediate variables.
- Rename cryptic identifiers to intention-revealing ones, updating all references.
- Prefer the language's idiomatic constructs over hand-rolled equivalents.

**Comments.** Cut the ones restating the code. Keep and sharpen the ones
explaining why. Rewrite stale or rambling ones into a short plain sentence.

## Performance

Measure before optimizing. Land the cheap, certain, structural wins; for
anything speculative, say so and recommend profiling rather than guessing.
Micro-optimizations that hurt readability without a measured payoff are
net-negative.

Structural problems worth fixing without profiling, because they're
correctness-adjacent:

- **Data access in a loop** — N+1 queries, work repeated per iteration that
  could be hoisted, a `.find` inside a `.map` turning O(n) into O(n²). Build a
  `Map`/`Set` lookup once instead.
- **Unbounded work** — fetching or rendering a whole collection when a page
  would do; a missing `limit`; a cache that only grows.
- **Repeated expensive computation** — the same heavy transform, sort, or parse
  recomputed when its inputs didn't change.
- **Leaks** — intervals, subscriptions, listeners, or timers never torn down;
  fetches with no `AbortController`.
- **Redundant passes** — parsing then re-stringifying the same data, or
  iterating a list several times where one pass would do.

Making something faster must not change *observable* behavior. If a change
alters timing, ordering, or effect semantics in a way a caller could notice,
flag it and ask — don't ship it as "just an optimization".

## Proving it worked

Lint and build confirm nothing is *referentially* broken. They do not confirm
behavior is unchanged. In a repo with tests, the suite is the evidence. In a
repo without, **the user's manual check is the evidence** — hand them a
checklist covering the flows that run through the refactored code, including
the callers you didn't think about, since that's where a refactor's risk lives.
