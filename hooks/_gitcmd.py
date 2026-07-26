#!/usr/bin/env python3
"""Shared parsing for the PreToolUse(Bash) git guards.

All three guards need the same thing: given a shell command that may be
compound (`cd x && git -C y commit -m ...`), find the git invocations of
interest and work out which repo -- and which branch -- each one actually
targets. Judging against the session's cwd instead is wrong in a worktree
setup: a commit from a feature worktree gets blocked whenever the main
checkout happens to sit on the base branch.

Every guard built on this fails OPEN. If the command can't be parsed, or the
base branch can't be determined unambiguously, the guard allows the operation
rather than wedging the session. A guard that blocks legitimate work gets
disabled by its user, at which point it protects nothing.
"""
import json
import os
import subprocess
import sys

SEPARATORS = {"&&", "||", ";", "|", "&"}
# git's own global options that consume the following token as their value.
# Without skipping these, `git -C /path commit` hides the subcommand.
GIT_GLOBAL_VALUE_OPTS = {"-C", "-c", "--git-dir", "--work-tree", "--namespace",
                         "--super-prefix", "--config-env", "--exec-path"}

DEFAULT_BRANCH_SH = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "scripts", "default-branch.sh")


def deny(reason):
    """Block the tool call, surfacing `reason` back to the model."""
    print(json.dumps({
        "hookSpecificOutput": {
            "hookEventName": "PreToolUse",
            "permissionDecision": "deny",
            "permissionDecisionReason": reason,
        }
    }))
    sys.exit(0)


def payload():
    """The hook's stdin JSON, or exit 0 if it isn't readable."""
    try:
        return json.load(sys.stdin)
    except (json.JSONDecodeError, ValueError):
        sys.exit(0)


def git(args, cwd):
    """Run a git command, returning stripped stdout or None."""
    try:
        out = subprocess.run(["git"] + args, cwd=cwd, capture_output=True,
                             text=True, timeout=5)
    except (OSError, subprocess.SubprocessError):
        return None
    return out.stdout.strip() if out.returncode == 0 else None


def current_branch(cwd):
    """Checked-out branch name, or None if detached or not a repo."""
    return git(["symbolic-ref", "--quiet", "--short", "HEAD"], cwd)


def base_branch(cwd):
    """The repo's base branch, or None if it can't be known unambiguously."""
    if not os.path.exists(DEFAULT_BRANCH_SH):
        return None
    try:
        proc = subprocess.run(["bash", DEFAULT_BRANCH_SH], cwd=cwd,
                              capture_output=True, text=True, timeout=10)
    except (OSError, subprocess.SubprocessError):
        return None
    # exit 3 = ambiguous, exit 1 = no branches. Only exit 0 is authoritative.
    return proc.stdout.strip() if proc.returncode == 0 else None


def resolve_cwd(cwd, path):
    """Apply a `cd`/-C argument to cwd. Absolute paths replace it outright."""
    if not path:
        return cwd
    return os.path.normpath(os.path.join(cwd, os.path.expanduser(path)))


def _git_c_path(seg):
    """The value of git's global -C, if this invocation has one."""
    i = 1
    while i < len(seg):
        tok = seg[i]
        if tok == "-C":
            return seg[i + 1] if i + 1 < len(seg) else None
        if tok in GIT_GLOBAL_VALUE_OPTS:
            i += 2
        elif tok.startswith("-"):
            i += 1
        else:
            break
    return None


def _subcommand_index(seg):
    """Index of git's subcommand, skipping global options and their values."""
    i = 1
    while i < len(seg):
        tok = seg[i]
        if tok in GIT_GLOBAL_VALUE_OPTS:
            i += 2                      # option plus its value
        elif tok.startswith("-"):
            i += 1                      # boolean flag, or --opt=value
        else:
            return i
    return -1


def _switch_target(args):
    """The branch a `git switch`/`checkout` leaves checked out, or None.

    Stops at `--`, so `git checkout -- somefile` (which restores a file and
    changes no branch) isn't mistaken for a switch to a branch named
    "somefile". Getting that wrong would make a later guard judge the merge
    against a branch that was never checked out.
    """
    for tok in args:
        if tok == "--":
            return None
        if not tok.startswith("-"):
            return tok
    return None


def walk(tokens, base_cwd, wanted):
    """Find git invocations of the `wanted` subcommands in a compound command.

    Yields dicts of {subcommand, args, cwd, branch}, where:
      cwd    -- the repo that segment runs in, after any earlier `cd` and its own -C
      branch -- the branch that will be checked out when it runs, if an earlier
                `git switch`/`git checkout` in the same command changed it.
                None means "unchanged; ask git at hook time."

    Tracking the switch matters: `git switch main && git merge feat/x` merges
    into main, but at hook time HEAD is still on feat/x.
    """
    segments, current = [], []
    for tok in tokens:
        if tok in SEPARATORS:
            segments.append(current)
            current = []
        else:
            current.append(tok)
    segments.append(current)

    found, cwd, switched = [], base_cwd, {}
    for seg in segments:
        if not seg:
            continue
        # `cd foo && git commit` targets foo, and the cd sticks for later segments.
        if seg[0] == "cd":
            cwd = resolve_cwd(cwd, seg[1]) if len(seg) > 1 else cwd
            continue
        if len(seg) < 2 or os.path.basename(seg[0]) != "git":
            continue
        idx = _subcommand_index(seg)
        if idx == -1:
            continue
        sub, args = seg[idx], seg[idx + 1:]
        seg_cwd = resolve_cwd(cwd, _git_c_path(seg))

        if sub in ("switch", "checkout"):
            target = _switch_target(args)
            # `switch -c new` / `checkout -b new` creates a branch; both still
            # leave that branch checked out, so either way it's the new HEAD.
            if target and target != "-":
                switched[seg_cwd] = target
            continue

        if sub in wanted:
            found.append({"subcommand": sub, "args": args, "cwd": seg_cwd,
                          "branch": switched.get(seg_cwd)})
    return found
