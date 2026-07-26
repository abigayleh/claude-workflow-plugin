#!/usr/bin/env python3
"""PreToolUse(Bash) guard: block `git merge` that would land on the base branch.

This is the plugin's firmest rule. Claude may merge freely between feature
branches, but integrating work into the base is the user's decision, made
through a pull request they open and review themselves. An agent that can
merge to main can undo every other guardrail in one command.

`git merge` merges INTO the currently checked-out branch, so the branch that
matters is the destination, not the argument. Two forms have to be caught:

    git switch main && git merge feat/x      # HEAD is still feat/x at hook time
    git -C ../main-checkout merge feat/x     # different repo entirely

_gitcmd.walk handles both. `git pull` is deliberately NOT blocked: pulling the
base branch from its own remote is a fast-forward of someone else's already
reviewed work, not this agent landing its own.
"""
import shlex
import sys

import _gitcmd as G

# main/master stay protected even when detection names a different base -- a
# repo whose base is `develop` still shouldn't get an agent-driven merge to main.
ALWAYS_PROTECTED = {"main", "master"}
# These don't integrate anything -- they wind back or resume an in-progress
# merge. Blocking `git merge --abort` on the base branch would trap the user
# in the exact state they're trying to escape.
NON_MERGING = {"--abort", "--continue", "--quit"}


def destination(hit):
    """The branch this merge would land on, or None if it can't be determined."""
    return hit["branch"] or G.current_branch(hit["cwd"])


def blocked_reason(hit):
    if any(a in NON_MERGING for a in hit["args"]):
        return None

    dest = destination(hit)
    if not dest:
        return None                     # detached HEAD or not a repo -- fail open

    protected = set(ALWAYS_PROTECTED)
    base = G.base_branch(hit["cwd"])
    if base:
        protected.add(base)
    if dest not in protected:
        return None

    return (
        "Merging into '%s' is blocked. This plugin takes work to ready-for-PR and "
        "stops -- landing it on the base branch is the user's call, made through a "
        "pull request they open.\n"
        "Instead: push the feature branch and report the `gh pr create` command.\n"
        "See the git-workflow skill." % dest
    )


def main():
    data = G.payload()
    command = (data.get("tool_input") or {}).get("command") or ""
    if "merge" not in command:
        sys.exit(0)

    try:
        tokens = shlex.split(command)
    except ValueError:
        sys.exit(0)

    for hit in G.walk(tokens, data.get("cwd") or ".", {"merge"}):
        reason = blocked_reason(hit)
        if reason:
            G.deny(reason)
    sys.exit(0)


if __name__ == "__main__":
    main()
