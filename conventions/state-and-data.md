# State and data-write conventions

One failure mode causes most state bugs: **the same server fact living in
several places that drift apart.** Every rule here pushes toward a single
source of truth.

The worked examples use React Query and Firestore because that's where these
rules were learned, but the principles apply to any client cache over any
remote store.

## Client state

- **The cache is the state.** Components read server data from the query layer;
  mutations update the cache. Don't mirror server data into component state and
  hand-sync it back through callbacks — that spawns N copies of one fact, and
  they will drift.
- **Don't store what you can compute.** Derived values calculated during render
  can't fall out of sync. Two sources of truth is one too many.
- **Do optimism inside the mutation, not in components.** The canonical shape:
  cancel in-flight queries, snapshot the current cache, apply the optimistic
  update, return the snapshot as rollback context; restore it on error;
  invalidate on settle. Optimism and rollback live together in one place, not
  spread across every caller.

  In React Query terms: `onMutate` cancels → `getQueryData` snapshots →
  `setQueryData` applies → returns context; `onError` restores; `onSettled`
  invalidates.
- **No optimistic update without a rollback.** If you can't cleanly roll back,
  be pessimistic instead — await the write, then update. Never leave
  applied-but-unconfirmed state with no path back.

## Effects

An effect that only computes state from other props or state should be a plain
calculation during render. The effect version renders, commits, then re-renders
— doing the work twice and adding a frame where the value is wrong.

Effects are for synchronizing with an **external** system: a subscription, a
DOM node, a non-React widget. Not for transforming data for display, not for
responding to a user event (that's the handler's job), and not for resetting
state when a prop changes (use a `key`).

Any hand-rolled fetch in an effect needs cleanup and an `AbortController`, or
it races and sets state after unmount. Prefer the project's data layer.

## Server writes

- **One auth posture: verify the token server-side, never trust a
  client-supplied user id.** See `security.md`.
- **Multi-document writes that must stay consistent use a transaction (for
  read-then-write) or a batch (for blind writes)** — never a sequence of
  separate writes that can half-fail and leave the data inconsistent.
- **One SDK on the server**, initialized once and imported — not a client SDK
  re-initialized per route.
- **Database security rules are the real boundary**, not your route handlers.

## Memoization

Measure first. With modern compilers most manual memoization is redundant, and
hand-added memoization has its own cost in noise and staleness risk. Add it for
a *measured* expensive computation, or to keep a reference stable for a
dependency array or a memoized child that genuinely re-renders too often. If
you can't say why it helps, don't add it.
