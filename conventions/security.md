# Security conventions

The single source of truth for security review in this plugin. The
`diff-review` skill and the `code-quality-reviewer` agent both read this file
rather than carrying their own copies — two checklists drift, one doesn't.

## Injection

- **SQL**: string-concatenated queries or unparameterized input. Require
  parameterized queries or prepared statements. An ORM's raw-query escape hatch
  counts as concatenation.
- **HTML/XSS**: unescaped user input reaching the DOM — `innerHTML`,
  `dangerouslySetInnerHTML`, template literals inserted into markup, `v-html`.
  Require sanitization or a safe API.
- **Command**: user input reaching a shell. Require an argument array, never a
  concatenated command string.
- **Path traversal**: user input in a filesystem path. Resolve the path and
  confirm it stays inside the intended root — a substring check is defeated by
  `../`.

## Secrets and data exposure

- Secrets, API keys, tokens, or PII in logs, error messages, client bundles, or
  committed files.
- Error responses that leak internals — stack traces, SQL, or filesystem paths
  returned to a client.
- Over-broad API responses: returning a whole user record where the caller
  needs a name and an id.

## Authorization

- **Verify identity server-side; never trust a client-supplied user id.** Every
  mutating route decodes the auth token and checks ownership. A route that
  trusts `userId` from the body or query is a hole even when a sibling route
  does the same — don't propagate it, flag it.
- New endpoints have the access control they should, including the ones that
  only read.
- **App-level checks are defence in depth; the database's own rules are the
  real boundary.** Anyone holding a public client config can bypass your routes
  and write directly. A route check is never the only guard.

## Dependencies

- New dependencies are a supply-chain decision, not a convenience. Flag every
  one added, with what it's for.
- Watch for typosquat-shaped names and packages with a single recent release.

## Review posture

- Flag issues with `file:line`.
- **Call out a security issue even when you also fix it.** A silent patch means
  the user never learns the pattern was there.
- If nothing is found, say so explicitly rather than staying quiet — silence
  reads as "not checked".
