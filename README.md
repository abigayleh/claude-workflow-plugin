# claude-workflow-plugin

An opinionated development pipeline for [Claude Code](https://claude.com/claude-code):
worktree-isolated branches, specialist subagents that write and review in
separate contexts, and hooks that make the guardrails **enforced rather than
advisory**.

The pipeline takes a feature from spec to ready-for-PR and stops. It never
merges to the base branch — that decision stays with a human, in a pull request
they open. Solo repos that don't want the ceremony can opt out per-repo with a
marker file; pushing to the base stays blocked either way.

```
worktree → detect stack → implement → verify → review → fix loop
        → push branch → re-review as the PR will look → hand off
```

---

## Why this exists

Prompting an agent to "be careful" doesn't scale. Under enough context pressure,
an instruction is a suggestion — the model will route around it with perfectly
good intentions. Three ideas run through everything here:

**1. Rules that matter get enforced in code, not in prose.**
Every non-negotiable is a `PreToolUse` hook that returns a `deny` decision the
model cannot argue with. Commits to the base branch, pushes to the base, merges
into the base, and reviewers editing the code they're reviewing are all blocked
at the tool layer. The prose in `conventions/` explains *why*; the hooks are
what actually hold.

**2. Separation of powers between agents.**
The reviewer and debugger have no write access to source. This isn't caution —
it's the point of the role. *A reviewer that can edit quietly fixes what it
finds, and the finding never reaches the user.* A reviewer that can't edit has
to write the problem down. Likewise `test-writer` has no Bash tool and never
reads the implementation, so its tests assert what the spec says rather than
what the code happens to do.

**3. Never claim verification that didn't happen.**
`scripts/detect-stack.py` reports the commands a project actually has. If
there's no test runner it says so, and the pipeline reports *"lint and build
passed; there is no test suite, so behavior is unverified"* instead of the
comfortable lie. Every check is labelled with what it does and doesn't prove.

---

## Install

```bash
/plugin marketplace add abigayleh/claude-workflow-plugin
/plugin install claude-workflow-plugin
```

Or point Claude Code at a local clone:

```bash
git clone https://github.com/abigayleh/claude-workflow-plugin
/plugin marketplace add ./claude-workflow-plugin
```

Requires `python3` and `git`. `gh` is optional (used only for the PR command
handed back at the end).

Verify the guards are firing in your Claude Code version:

```bash
python3 hooks/selftest.py     # 42 cases; exits non-zero on any failure
```

---

## What's in it

### Skills

| Skill | Does |
|---|---|
| `ship-feature` | Full spec → ready-for-PR pipeline (9 stages, two review passes) |
| `fix-bug` | Diagnose root cause → fix → confirm the bug is gone → PR |
| `refactor` | Behavior-preserving restructure, with an explicit honesty step about what's unproven |
| `git-workflow` | Worktree setup, branch naming, safe rebasing, conflict handling, PR handoff |
| `commit-message` | Single-line Conventional Commits, no bodies |
| `diff-review` | Pre-commit checklist: security, correctness, performance, scope |
| `dev-verify` | Start the app, hand the user a specific click-through checklist |
| `env-doctor` | Dependency/version/environment triage across six ecosystems |

### Agents

| Agent | Writes code? | Why |
|---|---|---|
| `code-writer` | Yes | Implements from a spec or a debugger's report |
| `code-quality-reviewer` | **No** | Must report findings, not silently patch them |
| `debugger` | **No** | Diagnoses root cause; hands the fix to `code-writer` |
| `ui-checker` | **No** | Reviews styling; explicitly cannot see the page and won't pretend to |
| `test-writer` | Tests only | No Bash, no memory, never reads the implementation |

`test-writer` is the only agent without persistent memory, deliberately: a
memory of "how this codebase works" is implementation knowledge under another
name, and it would destroy the independence that makes writing tests in parallel
with the implementation worth anything.

### Hooks

| Hook | Blocks |
|---|---|
| `check-commit-msg.py` | Commit bodies, multiple `-m`, messages from files, missing type prefix, commits on the base branch |
| `guard-push-main.py` | Pushes to the base branch, including `--all`/`--mirror` and `feat/x:main` refspecs |
| `guard-merge-main.py` | Any merge landing on the base branch, unless the repo opted out |
| `guard-agent-writes.py` | Read-only agents writing anywhere but their own memory directory |

The three git guards **fail open**: if the command can't be parsed or the base
branch can't be determined unambiguously, the operation is allowed. A guard
that blocks legitimate work gets switched off by its user, at which point it
protects nothing.

They also parse harder than a substring match. Each resolves the repo and branch
the command *actually targets* — through `cd`, through git's own `-C`, and
through a `git switch` earlier in the same compound command:

```bash
git switch main && git merge feat/x      # blocked: HEAD is still feat/x at hook time
git -C ../other-checkout commit -m "..."  # judged against ../other-checkout, not cwd
```

### Write grants

`guard-agent-writes.py` is the one hook that answers **allow** as well as deny.
A permission prompt that is always answered the same way trains the habit of
answering it without reading it, so the writes this workflow makes constantly
don't raise one:

| Write | Decision |
|---|---|
| Read-only agent, outside its memory directory | **deny** |
| File in a repo checked out on a feature branch | **allow**, no prompt |
| File matching a test path or naming convention | **allow**, no prompt |
| Anything else — on the base branch, or in no repo at all | normal prompt |

The deny is evaluated first, so a grant can never widen an agent meant to be
read-only. Unlike the git guards this one fails **closed**, to a prompt, since
the unsafe direction here is granting rather than blocking. Nothing it grants
can reach the base branch without passing the other three guards.

### Opting out of the merge block

`guard-merge-main.py` is the firmest rule here, but a solo project has no
reviewer on the other side of the pull request. Create the marker in a repo's
main checkout and `git-workflow` finishes by merging and removing the worktree
instead of handing off a PR:

```bash
mkdir -p .claude && touch .claude/allow-merge-to-base
```

It's read through git's common dir, so one file covers every worktree of that
repo — nothing to commit, nothing to keep in sync. **Pushing to the base stays
blocked regardless**, so merged work is local until you push it yourself.

### Conventions

Shared documents that skills and agents both read, so a rule lives in exactly
one place: `code-style.md`, `testing.md`, `git.md`, `security.md`,
`state-and-data.md`, `refactoring.md`.

The security checklist previously existed in two files and would have drifted.
Now `diff-review` and `code-quality-reviewer` both point at
`conventions/security.md`.

---

## Design notes

**Worktrees, not branch switching.** Every change gets its own folder.
`git switch` in a shared checkout changes the branch under whoever else is
working there; `git worktree add` never does, and is safe with a dirty tree.
This is what makes parallel agent work possible without two agents fighting over
one `HEAD`.

**Never assume the base branch is `main`.** `scripts/default-branch.sh` walks
from most authoritative (`origin/HEAD`) to least (a single local branch) and
**exits 3 rather than guessing** when the answer is genuinely ambiguous. Callers
treat that as "ask the user".

**Two review passes, not one.** The first reviews the code as written. The
second runs after the rebase and reviews the branch *as the pull request will
show it* — which is a different question, and where integration problems live.

**The fix loop is capped at three attempts.** Three failures means the problem
isn't what the agent thinks it is, and a fourth attempt won't discover that.
It stops and hands over.

**No commit bodies.** A body is where a change that couldn't be summarized goes
to hide. If one line won't cover it, the commit is doing too much.

---

## Recommended `CLAUDE.md`

A plugin can ship skills, agents, and hooks — but not a `CLAUDE.md`. Drop this
into your own to wire the pipeline into everyday behavior:

```markdown
## Workflow
- Every feature or bug fix gets its own branch in its own git worktree.
  Follow the `git-workflow` skill.
- Use `ship-feature` for new features, `fix-bug` for bugs, `refactor` for
  behavior-preserving restructures.
- Never merge, push, or commit to the base branch. Work ends at a pull
  request I open.

## Verifying
- Run `scripts/detect-stack.py` before claiming anything about tests.
  Report exactly which commands ran. Never say "tests pass" when nothing ran.
- For anything user-facing, use `dev-verify`: start the app, hand me a
  checklist, and wait. Don't screenshot or describe what the page looks like.

## Committing
After finishing any change: run `diff-review`, fix what's findable, flag what
needs my input, then commit with a single-line `type: summary` message.

## Exploring vs. implementing
For anything non-trivial, propose an approach and wait for confirmation before
writing code. Exception: changes under ~30 lines in a single file.
```

## Recommended permissions

The plugin ships **no** entries in your `permissions` block — that's a user
decision. The only grants it makes are the narrow, conditional ones
`guard-agent-writes.py` decides at call time, described above; they apply where
the workflow already isolates the change, and expire the moment you're back on
the base branch. One trap worth naming:

```jsonc
{
  "permissions": {
    "deny": ["Read(**/.env)", "Read(**/.env.*)"],
    "allow": ["Bash(*)"]        // ← defeats the deny above: `cat .env` still works
  }
}
```

Denying `Read` on a path does nothing while `Bash(*)` is allowed. Either scope
Bash to specific commands, or accept that `.env` contents are reachable and
don't rely on that deny rule for anything real.

---

## Repository layout

```
.claude-plugin/plugin.json   Manifest
agents/                      5 subagent definitions
skills/                      8 skills (one folder each, SKILL.md inside)
hooks/
  hooks.json                 Event wiring
  _gitcmd.py                 Shared git-command parsing for the three git guards
  selftest.py                42 allow/deny/grant cases against real throwaway repos
conventions/                 6 shared standards documents
scripts/
  detect-stack.py            Project → real test/lint/build/dev commands, as JSON
  default-branch.sh          Base branch, or a refusal to guess
  start-dev.sh               Start any detected dev server, wait for its port
```

## License

MIT
