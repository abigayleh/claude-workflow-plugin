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
# ALLOW means the hook said nothing, so the permission prompt still applies.
# GRANT is an explicit allow that skips the prompt. Collapsing the two would
# let a hook that silently stopped granting still pass every case.
ALLOW, GRANT, DENY = "allow", "grant", "deny"


def run_hook(script, payload):
    """Feed a payload to a guard. Returns (ALLOW|GRANT|DENY, reason)."""
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
    verdict = decision["permissionDecision"]
    return (GRANT if verdict == ALLOW else verdict,
            decision["permissionDecisionReason"])


def bash(cmd, cwd):
    return {"tool_input": {"command": cmd}, "cwd": cwd}


def write(path, cwd, agent=None):
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


def make_worktree(repo, path, branch):
    """A second working tree of `repo`, sharing its git common dir."""
    subprocess.run(["git", "worktree", "add", "-q", "-b", branch, path],
                   cwd=repo, check=True, capture_output=True)
    return path


def opt_in(repo):
    """Drop the merge-to-base marker in a repo's main checkout."""
    os.makedirs(os.path.join(repo, ".claude"), exist_ok=True)
    open(os.path.join(repo, ".claude", "allow-merge-to-base"), "w").close()
    return repo


def cases(tmp):
    base = make_repo(tmp, "on-base")                                  # on main
    feat = make_repo(tmp, "on-feat", ("main", "feat/x"), "feat/x")    # on feat/x

    # Opted in vs not, each with a worktree sitting on `master`. Merging there
    # is protected, and the marker can only be found via the common git dir --
    # it lives in the main checkout, not in the worktree.
    # Each gets its own repo: adding a `master` worktree to a repo whose only
    # branch was `main` makes its base ambiguous, which quietly defuses the
    # other guards' cases against it.
    opted = opt_in(make_repo(tmp, "opted-in"))
    opted_wt = make_worktree(opted, os.path.join(tmp, "opted-in-wt"), "master")
    strict = make_repo(tmp, "strict")
    strict_wt = make_worktree(strict, os.path.join(tmp, "strict-wt"), "master")

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

        # --- guard-merge-main: the .claude/allow-merge-to-base opt-out ---
        ("merge", "opted-in repo may merge to its base",
         "guard-merge-main.py", bash("git merge feat/x", opted), ALLOW),
        ("merge", "opt-out marker is found from a worktree via the common dir",
         "guard-merge-main.py", bash("git merge feat/x", opted_wt), ALLOW),
        ("merge", "a worktree without the marker is still blocked",
         "guard-merge-main.py", bash("git merge feat/x", strict_wt), DENY),
        ("merge", "-C into an opted-in repo from elsewhere",
         "guard-merge-main.py", bash("git -C %s merge feat/x" % opted, feat), ALLOW),

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
         "guard-agent-writes.py", write("src/app.js", feat, "code-writer"), GRANT),

        # --- guard-agent-writes: grants that skip the permission prompt ---
        ("write-grants", "editing on a feature branch",
         "guard-agent-writes.py", write("src/app.js", feat), GRANT),
        ("write-grants", "editing while sitting on the base branch",
         "guard-agent-writes.py", write("src/app.js", base), ALLOW),
        ("write-grants", "a conventionally-named base other than main/master",
         "guard-agent-writes.py",
         write("src/app.js", make_repo(tmp, "on-develop", ("develop",))), ALLOW),
        ("write-grants", "a test file, even on the base branch",
         "guard-agent-writes.py", write("tests/app.test.js", base), GRANT),
        ("write-grants", "a test file by naming convention alone",
         "guard-agent-writes.py", write("src/test_parser.py", base), GRANT),
        ("write-grants", "a source file in no repo at all",
         "guard-agent-writes.py", write("loose.js", tmp), ALLOW),
        ("write-grants", "an ancestor directory named e2e grants nothing",
         "guard-agent-writes.py",
         write("src/app.js", make_repo(tmp, "e2e")), ALLOW),
        ("write-grants", "read-only agents are not granted their own tests",
         "guard-agent-writes.py",
         write("tests/app.test.js", feat, "debugger"), DENY),
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
