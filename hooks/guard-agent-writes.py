#!/usr/bin/env python3
"""PreToolUse(Edit|Write|NotebookEdit) gate: read-only agents out, branch work through.

Two jobs, in that order -- the denial is checked first so a grant can never
widen an agent that was meant to be read-only.

DENY. Setting `memory:` on a subagent auto-grants Write/Edit so it can curate
its memory directory. The reviewer, debugger and ui-checker agents are meant to
report, not patch -- this restores that constraint: each may write inside its
own agent-memory directory and nowhere else. The distinction matters more than
it looks. A reviewer that can edit will quietly fix what it finds, and the
finding never reaches the user. A reviewer that cannot edit has to write the
problem down.

Paths are resolved before comparison -- a substring check alone is defeated by
`agent-memory/debugger/../../../src/evil.js`.

ALLOW. Editing a file in a repo that is checked out on a feature branch is the
normal, expected state of this workflow, and nothing written there can reach
the base branch without passing the other three guards. Confirming each such
edit is a prompt that is always answered the same way, which trains the habit
of answering it without reading it. Test files are granted wherever they sit,
since a test asserts behavior rather than changing it.

Anything else -- editing while sitting on a conventional base branch, a file in
no repo at all, a branch that can't be determined -- gets no decision, leaving
the normal permission prompt in place. The git guards fail open because a guard
that blocks real work gets switched off; this one fails *closed*, to a prompt,
because the unsafe direction here is granting rather than blocking.

It runs on every edit, so it stays cheap: one `git symbolic-ref` and no
network. See NEVER_FEATURE.

On the payload field name: the key identifying the calling subagent has varied
across Claude Code versions, so several candidates are checked. If none is
present the hook does not deny, which means a silently-renamed field degrades
to "no enforcement" rather than "everything blocked". Run `hooks/selftest.py`
to confirm the guard is actually firing in your version.
"""
import os
import re
import sys

import _gitcmd as G

READ_ONLY_AGENTS = {"code-quality-reviewer", "debugger", "ui-checker"}
AGENT_KEYS = ("agent_type", "subagent_type", "agentType", "subagentType")
MEMORY_PARENTS = (".claude/agent-memory", ".claude/agent-memory-local")

# Conventional base-branch names, matching what default-branch.sh probes for.
# This deliberately does NOT call default-branch.sh: that can reach the network
# (`git ls-remote`) in a repo without origin/HEAD, and this hook runs on every
# single edit. "Is this a feature branch" doesn't need an authoritative answer
# -- being on none of these names is enough, and it costs one local git call.
NEVER_FEATURE = {"main", "master", "trunk", "develop", "development"}
TEST_DIRS = {"test", "tests", "__tests__", "spec", "specs", "e2e"}
TEST_FILE = re.compile(r"(^test_|_test\.|\.test\.|_spec\.|\.spec\.|Test\.|Spec\.)")


def calling_agent(data):
    """The read-only agent making this call, or None."""
    for scope in (data, data.get("tool_input") or {}):
        for key in AGENT_KEYS:
            value = scope.get(key)
            if value in READ_ONLY_AGENTS:
                return value
    return None


def is_test_path(resolved, root):
    """Judged relative to the project: an *ancestor* directory that happens to
    be called `spec` or `e2e` must not grant everything underneath it."""
    rel = os.path.relpath(resolved, root)
    if rel.startswith(os.pardir):
        rel = os.path.basename(resolved)     # outside the project entirely
    parts = rel.split(os.sep)
    return bool(TEST_DIRS.intersection(parts) or TEST_FILE.search(parts[-1]))


def nearest_dir(resolved):
    """The closest existing ancestor directory -- the file may not exist yet."""
    path = os.path.dirname(resolved)
    while path and not os.path.isdir(path):
        parent = os.path.dirname(path)
        if parent == path:
            return None
        path = parent
    return path or None


def feature_branch(resolved):
    """The feature branch this path sits on, or None if it isn't on one."""
    directory = nearest_dir(resolved)
    if not directory:
        return None
    branch = G.current_branch(directory)
    return None if not branch or branch in NEVER_FEATURE else branch


def enforce_read_only(agent, target, cwd):
    """Read-only agents may write inside their own memory directory only."""
    allowed = [os.path.realpath(os.path.join(cwd, parent, agent))
               for parent in MEMORY_PARENTS]
    if any(target == a or target.startswith(a + os.sep) for a in allowed):
        sys.exit(0)

    G.deny(
        "%s is a read-only agent: it reports findings, it does not edit code. "
        "The only writable location is its own memory directory "
        "(.claude/agent-memory/%s/). Blocked write to: %s -- report this as a "
        "finding in your output instead of changing the file."
        % (agent, agent, target)
    )


def main():
    data = G.payload()
    tool_input = data.get("tool_input") or {}
    raw = tool_input.get("file_path") or tool_input.get("notebook_path") or ""
    # realpath both sides, or /tmp vs /private/tmp makes every path look
    # "outside the project" on macOS.
    cwd = os.path.realpath(data.get("cwd") or os.getcwd())
    agent = calling_agent(data)

    if not raw:
        if agent:
            G.deny("%s is a read-only agent and this write has no resolvable "
                   "path." % agent)
        sys.exit(0)

    target = os.path.realpath(os.path.join(cwd, os.path.expanduser(raw)))

    if agent:
        enforce_read_only(agent, target, cwd)

    branch = feature_branch(target)
    if branch:
        G.allow("Editing on feature branch '%s' -- isolated from the base "
                "branch, which no guard here will let it reach unreviewed."
                % branch)
    if is_test_path(target, cwd):
        G.allow("Test file -- asserts behavior rather than changing it.")
    sys.exit(0)                         # no decision: fall through to the prompt


if __name__ == "__main__":
    main()