#!/usr/bin/env python3
"""PreToolUse(Bash) guard for `git commit`.

Two rules:
  1. The message must be a single Conventional Commits line -- no body.
  2. Commits go to a feature branch, never to the repo's base branch.

Rule 1 exists because a commit body is where an agent hides a change it
couldn't summarize. If the summary doesn't fit in one line, the commit is
doing too much and should be split.

See _gitcmd.py for how the target repo/branch is resolved, and why both rules
fail open.
"""
import re
import shlex
import sys

import _gitcmd as G

TYPES = ("build", "chore", "ci", "docs", "feat", "fix", "perf",
         "refactor", "revert", "style", "test")
SUBJECT_RE = re.compile(r"^(?:%s)(?:\([^()]+\))?!?: .+" % "|".join(TYPES))
# Flags that pull a commit message from somewhere other than an inline -m.
FILE_FLAGS = {"-F", "--file", "-t", "--template", "-C", "--reuse-message",
              "-c", "--reedit-message", "--squash", "--fixup"}


def base_branch_block(cwd, branch):
    """Reason to block, or None. Fails open on any ambiguity or error."""
    current = branch or G.current_branch(cwd)
    if not current:
        return None                  # detached HEAD or not a repo -- not our call
    base = G.base_branch(cwd)
    if not base or base != current:
        return None
    return ("You're on '%s', the repo's base branch. Commits belong on a feature "
            "branch -- this plugin never lands work on the base itself.\n"
            "Create one first:\n"
            "  git switch -c feat/short-description\n"
            "See the git-workflow skill." % current)


def extract_messages(args):
    """Return (messages, uses_file_flag, has_no_edit, has_amend)."""
    messages, uses_file, no_edit, amend = [], False, False, False
    i = 0
    while i < len(args):
        tok = args[i]
        if tok == "--no-edit":
            no_edit = True
        elif tok == "--amend":
            amend = True
        elif tok in FILE_FLAGS or any(
                tok.startswith(f + "=") for f in FILE_FLAGS if f.startswith("--")):
            uses_file = True
        elif tok in ("-m", "--message"):
            if i + 1 < len(args):
                messages.append(args[i + 1])
                i += 1
        elif tok.startswith("--message="):
            messages.append(tok[len("--message="):])
        elif tok.startswith("-") and not tok.startswith("--") and "m" in tok[1:]:
            # Combined short flags: -am "msg", -mfoo, -am"foo"
            flags = tok[1:]
            rest = flags[flags.index("m") + 1:]
            if rest:
                messages.append(rest)
            elif i + 1 < len(args):
                messages.append(args[i + 1])
                i += 1
        i += 1
    return messages, uses_file, no_edit, amend


def main():
    data = G.payload()
    command = (data.get("tool_input") or {}).get("command") or ""
    if "commit" not in command:
        sys.exit(0)

    try:
        tokens = shlex.split(command)
    except ValueError:
        # Unbalanced quotes usually mean a heredoc-wrapped multi-line message.
        if re.search(r"\bgit\b.*\bcommit\b", command, re.S) and "\n" in command:
            G.deny("Commit message appears to span multiple lines (heredoc). "
                   "Use a single inline message: git commit -m \"type: summary\"")
        sys.exit(0)

    for hit in G.walk(tokens, data.get("cwd") or ".", {"commit"}):
        reason = base_branch_block(hit["cwd"], hit["branch"])
        if reason:
            G.deny(reason)

        messages, uses_file, no_edit, amend = extract_messages(hit["args"])

        if uses_file:
            G.deny("Commit messages must be inline and single-line. "
                   "Use: git commit -m \"type: summary\" (no -F/-t/-C/--fixup).")

        if not messages:
            if amend and no_edit:
                continue  # `--amend --no-edit` reuses an already-validated message
            G.deny("No -m given, so git would open an editor and hang. "
                   "Use: git commit -m \"type: summary\"")

        if len(messages) > 1:
            G.deny("Multiple -m flags produce a commit body (git joins them as "
                   "paragraphs). Use exactly one -m with a single-line summary.")

        msg = messages[0]
        if "$(" in msg or "<<" in msg or "`" in msg:
            G.deny("Write the commit message literally, not via command "
                   "substitution or a heredoc -- that form is how bodies creep in. "
                   "Use: git commit -m \"type: summary\"")

        if "\n" in msg or "\r" in msg:
            G.deny("Commit message must be a single line with no body. "
                   "Got a multi-line message; keep only the `type: summary` line.")

        if not SUBJECT_RE.match(msg):
            G.deny("Commit message must match `type: summary` (Conventional "
                   "Commits). Allowed types: %s. Got: %r"
                   % (", ".join(TYPES), msg))

    sys.exit(0)


if __name__ == "__main__":
    main()
