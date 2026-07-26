#!/usr/bin/env python3
"""Run the guards against crafted payloads and assert allow/deny.

A PreToolUse guard fails open by design, which means a broken one is
indistinguishable from a working one during normal use -- it just stops
blocking and nobody notices. This exercises each guard against the cases it
exists for, including the ones that need a real repo on disk (committing on
the base branch, `git switch main && git merge`).

Usage:  python3 hooks/selftest.py        # exits non-zero if any case fails
"""
import json
import os
import shutil
import subprocess
import sys
import tempfile

HOOKS = os.path.dirname(os.path.abspath(__file__))
ALLOW, DENY = "allow", "deny"


def run_hook(script, payload):
    """Feed a payload to a guard. Returns (ALLOW|DENY, reason)."""
    proc = subprocess.run([sys.executable, os.path.join(HOOKS, script)],
                          input=json.dumps(payload), capture_output=True,
                          text=True, timeout=30)
    if proc.returncode != 0:
        return "error", proc.stderr.strip()
    out = proc.stdout.strip()
    if not out:
        return ALLOW, ""
    try:
        decision = json.loads(out)["hookSpecificOutput"]
    except (ValueError, KeyError):
        return "error", "unparseable output: %r" % out
    return decision["permissionDecision"], decision["permissionDecisionReason"]


def bash(cmd, cwd):
    return {"tool_input": {"command": cmd}, "cwd": cwd}


def write(path, cwd, agent):
    return {"tool_input": {"file_path": path}, "cwd": cwd, "agent_type": agent}


def make_repo(root, name, branches=("main",), checkout=None):
    """A throwaway repo with a root commit, so branch detection has something real."""
    path = os.path.join(root, name)
    os.makedirs(path)
    run = lambda *a: subprocess.run(["git"] + list(a), cwd=path, check=True,
                                    capture_output=True)
    run("init", "-b", branches[0], "-q")
    run("config", "user.email", "selftest@example.com")
    run("config", "user.name", "selftest")
    run("commit", "-q", "--allow-empty", "-m", "chore: root")
    for b in branches[1:]:
        run("branch", b)
    if checkout:
        run("switch", "-q", checkout)
    return path


def cases(tmp):
    base = make_repo(tmp, "on-base")                                  # on main
    feat = make_repo(tmp, "on-feat", ("main", "feat/x"), "feat/x")    # on feat/x

    return [
        # --- check-commit-msg: message format ---
        ("commit-msg", "valid conventional commit",
         "check-commit-msg.py", bash('git commit -m "feat: add thing"', feat), ALLOW),
        ("commit-msg", "no type prefix",
         "check-commit-msg.py", bash('git commit -m "added a thing"', feat), DENY),
        ("commit-msg", "two -m flags produce a body",
         "check-commit-msg.py", bash('git commit -m "feat: a" -m "details"', feat), DENY),
        ("commit-msg", "no -m would open an editor",
         "check-commit-msg.py", bash("git commit", feat), DENY),
        ("commit-msg", "message sourced from a file",
         "check-commit-msg.py", bash("git commit -F msg.txt", feat), DENY),
        ("commit-msg", "combined short flags -am",
         "check-commit-msg.py", bash('git commit -am "fix: y"', feat), ALLOW),
        ("commit-msg", "scope and breaking-change marker",
         "check-commit-msg.py", bash('git commit -m "feat(api)!: drop v1"', feat), ALLOW),
        ("commit-msg", "command substitution in message",
         "check-commit-msg.py", bash('git commit -m "feat: $(cat notes)"', feat), DENY),

        # --- check-commit-msg: branch, judged against the targeted repo ---
        ("commit-msg", "commit while on the base branch",
         "check-commit-msg.py", bash('git commit -m "feat: x"', base), DENY),
        ("commit-msg", "-C targets a repo sitting on the base branch",
         "check-commit-msg.py", bash('git -C %s commit -m "feat: x"' % base, feat), DENY),
        ("commit-msg", "cd into a feature worktree first",
         "check-commit-msg.py", bash('cd %s && git commit -m "feat: x"' % feat, base), ALLOW),

        # --- guard-merge-main ---
        ("merge", "merge while on the base branch",
         "guard-merge-main.py", bash("git merge feat/x", base), DENY),
        ("merge", "switch to main first, then merge",
         "guard-merge-main.py", bash("git switch main && git merge feat/x", feat), DENY),
        ("merge", "-C into a repo on the base branch",
         "guard-merge-main.py", bash("git -C %s merge feat/x" % base, feat), DENY),
        ("merge", "merge between feature branches",
         "guard-merge-main.py", bash("git merge feat/other", feat), ALLOW),
        ("merge", "git pull is not an agent-driven merge",
         "guard-merge-main.py", bash("git pull", base), ALLOW),
        ("merge", "--abort winds back, it doesn't integrate",
         "guard-merge-main.py", bash("git merge --abort", base), ALLOW),
        ("merge", "--continue resumes an existing merge",
         "guard-merge-main.py", bash("git merge --continue", base), ALLOW),
        ("merge", "checkout -- file is not a branch switch",
         "guard-merge-main.py",
         bash("git checkout -- README.md && git merge feat/x", base), DENY),

        # --- guard-push-main ---
        ("push", "explicit push to main",
         "guard-push-main.py", bash("git push origin main", feat), DENY),
        ("push", "refspec renaming onto main",
         "guard-push-main.py", bash("git push origin feat/x:main", feat), DENY),
        ("push", "push --all sweeps the base along",
         "guard-push-main.py", bash("git push --all origin", feat), DENY),
        ("push", "bare push while on the base branch",
         "guard-push-main.py", bash("git push", base), DENY),
        ("push", "push a feature branch",
         "guard-push-main.py", bash("git push origin feat/x", feat), ALLOW),
        ("push", "force-with-lease on a feature branch",
         "guard-push-main.py", bash("git push --force-with-lease origin feat/x", feat), ALLOW),

        # --- guard-agent-writes ---
        ("agent-writes", "read-only agent edits source",
         "guard-agent-writes.py", write("src/app.js", feat, "debugger"), DENY),
        ("agent-writes", "read-only agent writes its own memory",
         "guard-agent-writes.py",
         write(".claude/agent-memory/debugger/MEMORY.md", feat, "debugger"), ALLOW),
        ("agent-writes", "traversal out of the memory dir",
         "guard-agent-writes.py",
         write(".claude/agent-memory/debugger/../../../src/evil.js", feat, "debugger"), DENY),
        ("agent-writes", "read-only agent writes another agent's memory",
         "guard-agent-writes.py",
         write(".claude/agent-memory/code-writer/MEMORY.md", feat, "debugger"), DENY),
        ("agent-writes", "code-writer is allowed to write source",
         "guard-agent-writes.py", write("src/app.js", feat, "code-writer"), ALLOW),
    ]


def main():
    tmp = tempfile.mkdtemp(prefix="cwp-selftest-")
    failures = []
    try:
        for group, name, script, payload, expected in cases(tmp):
            got, reason = run_hook(script, payload)
            ok = got == expected
            print("%s %-13s %s" % ("PASS" if ok else "FAIL", group, name))
            if not ok:
                failures.append("%s / %s: expected %s, got %s%s"
                                % (group, name, expected, got,
                                   " (%s)" % reason.splitlines()[0] if reason else ""))
    finally:
        shutil.rmtree(tmp, ignore_errors=True)

    print()
    if failures:
        print("%d failure(s):" % len(failures))
        for f in failures:
            print("  - %s" % f)
        sys.exit(1)
    print("All guard cases passed.")


if __name__ == "__main__":
    main()
