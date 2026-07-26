# Code style conventions

Optimized for skimming. Someone reading this code for the first time should be
able to tell what it does without reconstructing it.

## General

- Simple, readable code over clever code. Explicit beats compact.
- Short, focused files. One responsibility each.
- **Comments: max two lines, only when non-obvious.** Explain *why* — intent,
  trade-offs, gotchas. Never restate what the code already says.
- Less code is better. The best change often deletes more than it adds.

## Match the codebase before your own preferences

Read enough of the surrounding code to learn its conventions — naming, folder
structure, error handling, import style — and follow them. A change that's
stylistically correct but locally foreign is still a bad change.

When an area has two competing patterns and one is clearly the right one,
migrate toward it and **flag the outlier to the user** rather than silently
propagating either.

## Reusability

- Repeated logic → extract to a shared function or hook and import it.
- Repeated components → extract and reuse.
- Never duplicate logic or markup. The second copy is where the bug lives.
- Complex functions or components → their own file.

## Dependencies

Avoid adding them unless genuinely necessary. Every dependency is a
supply-chain, bundle-size, and maintenance decision. If one is needed, flag it
explicitly in the summary — never add it silently.

## Styling

- Write only CSS that overrides a non-default value.
- Repeated styles → a global stylesheet, reused via class names.
- Prefer global styles over scoped or inline ones.
- No style duplication.

## Error handling

Handle the unhappy paths — empty input, null, network failure — rather than
assuming the happy one. Surface failures through **one convention per app**:
pick inline errors or toasts and use it everywhere. Never `alert()`; it blocks
and it doesn't match anything else in the product.

## Scope discipline

- Implement the smallest correct change that fully satisfies the requirement.
- Don't gold-plate, and don't refactor unrelated code on the way past.
- Never silently change files outside the task.
