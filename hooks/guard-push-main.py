#!/usr/bin/env python3
"""PreToolUse(Bash) guard: block `git push` that targets the base branch.

Pushing feature branches is expected -- the pipeline pushes one before handing
off a PR. Pushing to the base is not: that bypasses the pull request entirely,
which is the whole point of stopping at ready-for-PR.

Blocked when the destination refspec names a protected branch, when a bare
`git push` would push a currently-protected branch, or when --all/--mirror
would sweep the base along with everything else. Fails OPEN on ambiguity.
"""
import shlex
import sys

import _gitcmd as G

ALWAYS_PROTECTED = {"main", "master"}
# push flags that consume the following token as their value.
PUSH_VALUE_OPTS = {"--repo", "-o", "--push-option", "--receive-pack",
                   "--exec", "--force-with-lease", "--recurse-submodules"}


def protected_set(cwd):
    names = set(ALWAYS_PROTECTED)
    base = G.base_branch(cwd)
    if base:
        names.add(base)
    return names


def dest_branch(refspec):
    """Destination ref of a refspec: right of ':' (or the whole thing), no +."""
    spec = refspec.lstrip("+")
    dest = spec.split(":", 1)[1] if ":" in spec else spec
    return dest.rsplit("/", 1)[-1]


def blocked_reason(hit):
    args, cwd = hit["args"], hit["cwd"]
    positionals, wide = [], False
    i = 0
    while i < len(args):
        tok = args[i]
        if tok in ("--all", "--mirror"):
            wide = True                 # pushes every branch, base included
        elif tok in PUSH_VALUE_OPTS:
            i += 1
        elif not tok.startswith("-"):
            positionals.append(tok)
        i += 1

    if wide:
        return ("`git push --all/--mirror` would push the base branch. Push a "
                "single feature branch instead.")

    protected = protected_set(cwd)
    refspecs = positionals[1:]          # first positional is the remote

    for r in refspecs:
        if r == "HEAD":
            dest = hit["branch"] or G.current_branch(cwd)
        else:
            dest = dest_branch(r)
        if dest in protected:
            return _reason(dest)

    if not refspecs:                    # bare `git push` -> current branch
        cur = hit["branch"] or G.current_branch(cwd)
        if cur in protected:
            return _reason(cur)
    return None


def _reason(branch):
    return ("Pushing to '%s' is blocked -- it bypasses the pull request. Push the "
            "feature branch instead, then report the `gh pr create` command and "
            "let the user open the PR." % branch)


def main():
    data = G.payload()
    command = (data.get("tool_input") or {}).get("command") or ""
    if "push" not in command:
        sys.exit(0)

    try:
        tokens = shlex.split(command)
    except ValueError:
        sys.exit(0)

    for hit in G.walk(tokens, data.get("cwd") or ".", {"push"}):
        reason = blocked_reason(hit)
        if reason:
            G.deny(reason)
    sys.exit(0)


if __name__ == "__main__":
    main()
