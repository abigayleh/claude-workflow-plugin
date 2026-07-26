#!/usr/bin/env python3
"""PreToolUse(Edit|Write|NotebookEdit) guard for read-only subagents.

Setting `memory:` on a subagent auto-grants Write/Edit so it can curate its
memory directory. The reviewer and debugger agents are meant to report, not
patch -- this hook restores that constraint: each may write inside its own
agent-memory directory and nowhere else.

The distinction matters more than it looks. A reviewer that can edit will
quietly fix what it finds, and the finding never reaches the user. A reviewer
that cannot edit has to write the problem down.

Paths are resolved before comparison -- a substring check alone is defeated by
`agent-memory/debugger/../../../src/evil.js`.

On the payload field name: the key identifying the calling subagent has varied
across Claude Code versions, so several candidates are checked. If none is
present the hook allows the write, which means a silently-renamed field
degrades to "no enforcement" rather than "everything blocked". Run
`hooks/selftest.py` to confirm the guard is actually firing in your version.
"""
import json
import os
import sys

READ_ONLY_AGENTS = {"code-quality-reviewer", "debugger", "ui-checker"}
AGENT_KEYS = ("agent_type", "subagent_type", "agentType", "subagentType")
MEMORY_PARENTS = (".claude/agent-memory", ".claude/agent-memory-local")


def deny(reason):
    print(json.dumps({
        "hookSpecificOutput": {
            "hookEventName": "PreToolUse",
            "permissionDecision": "deny",
            "permissionDecisionReason": reason,
        }
    }))
    sys.exit(0)


def calling_agent(data):
    """The read-only agent making this call, or None."""
    for scope in (data, data.get("tool_input") or {}):
        for key in AGENT_KEYS:
            value = scope.get(key)
            if value in READ_ONLY_AGENTS:
                return value
    return None


def main():
    try:
        data = json.load(sys.stdin)
    except (json.JSONDecodeError, ValueError):
        sys.exit(0)

    agent = calling_agent(data)
    if not agent:
        sys.exit(0)

    tool_input = data.get("tool_input") or {}
    raw = tool_input.get("file_path") or tool_input.get("notebook_path") or ""
    if not raw:
        deny("%s is a read-only agent and this write has no resolvable path." % agent)

    cwd = data.get("cwd") or os.getcwd()
    resolved = os.path.realpath(os.path.join(cwd, os.path.expanduser(raw)))

    # The agent may only write within its OWN memory directory.
    allowed = [os.path.realpath(os.path.join(cwd, parent, agent))
               for parent in MEMORY_PARENTS]
    if any(resolved == a or resolved.startswith(a + os.sep) for a in allowed):
        sys.exit(0)

    deny(
        "%s is a read-only agent: it reports findings, it does not edit code. "
        "The only writable location is its own memory directory "
        "(.claude/agent-memory/%s/). Blocked write to: %s -- report this as a "
        "finding in your output instead of changing the file."
        % (agent, agent, resolved)
    )


if __name__ == "__main__":
    main()
