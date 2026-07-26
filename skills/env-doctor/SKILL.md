---
name: env-doctor
description: Diagnose dependency, version, and environment problems — wrong interpreter or runtime on PATH, unactivated virtualenv, lockfile and manifest drift, duplicate or conflicting package versions. Per-ecosystem commands for Node, Python, Rust, Go, Java, and Ruby.
when_to_use: A "module not found" or "cannot find package" error, a version mismatch, or a works-locally-but-fails-in-CI problem where the environment is the likely cause rather than the code.
allowed-tools: Bash, Read, Grep, Glob
---

# Environment and dependency triage

For problems where the *environment* is the suspect, not the code. If the code
is the suspect, use the `debugger` agent instead.

Identify the stack first:

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/detect-stack.py"
```

Its `notes` already flag several classic causes — multiple lockfiles, a
placeholder test script, workspace layouts.

## The pattern behind most of these

Code was written against one version of a dependency, and then either a lockfile
update pulled in a breaking major, or two environments (local, CI, prod) resolve
differently because a version wasn't pinned. **Diff the installed version
against the manifest-declared version against the lockfile-pinned version** —
that usually surfaces it in one step.

The second most common cause is simpler: the command is running against a
different interpreter or runtime than you think. Check that before anything else.

## Node

```bash
node -v && npm -v            # versions actually in use
which node                   # which install is on PATH (nvm/volta mismatches)
npm ls <package>             # installed version + resolution tree
npm ls                       # full tree; flags "invalid"/"missing"
npm outdated                 # what's behind the manifest
rm -rf node_modules package-lock.json && npm install    # when state is suspect
```

- Multiple lockfiles (`package-lock.json` *and* `yarn.lock` *and*
  `pnpm-lock.yaml`) is itself the bug — different tools resolve differently.
- Nested `node_modules` holding two versions of the same package is the classic
  cause of "two different instances of the same singleton/class".

## Python

```bash
which python && python --version    # the interpreter actually running
echo $VIRTUAL_ENV                   # is the venv actually activated?
pip show <package>                  # installed version + location
pip check                           # reports incompatible installed versions
python -c "import sys; print(sys.path)"    # which site-packages is in play
```

An unactivated venv is far and away the most common cause of
`ModuleNotFoundError` despite `pip install` having "worked".

- poetry: `poetry show <pkg>`, `poetry check`, `poetry env info`
- uv: `uv pip list`, `uv sync --locked`
- conda: `conda list`, `conda env list`

## Rust

```bash
cargo tree                   # full graph, flags conflicts
cargo tree -d                # duplicated crates at different versions
cargo update -p <crate> --dry-run
cargo check
```

## Go

```bash
go list -m all               # resolved module graph
go mod tidy                  # reconcile go.mod/go.sum with actual imports
go mod why <module>          # why is this here at all
```

## Java

```bash
mvn dependency:tree          # resolved tree, flags conflicts
mvn dependency:analyze       # unused/undeclared
./gradlew dependencies
./gradlew dependencyInsight --dependency <name>
```

## Ruby

```bash
bundle list                  # installed gems + versions
bundle check                 # is Gemfile.lock satisfied?
bundle exec <cmd>            # run against bundled versions, not system gems
```

## Any stack

```bash
echo $PATH | tr ':' '\n'     # which binaries resolve first
env | sort                   # redact secrets before sharing this
docker --version && docker ps   # if containerized, the container's env is the one that matters
```

**Don't `cat .env` and paste it into the conversation.** Check that the expected
keys are *present* without printing values:

```bash
cut -d= -f1 .env 2>/dev/null    # key names only
```
