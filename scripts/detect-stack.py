#!/usr/bin/env python3
"""Report the verification commands a repo actually has, as JSON.

The pipeline skills call this instead of assuming a stack. Every field is
either a command that was found in the project, or null -- never a guess at
what the command "should" be. A skill that gets null for `test` reports that
no test runner exists; it does not invent one, and it does not claim tests
passed.

Usage:  detect-stack.py [path]      (default: cwd)

Output keys:
  ecosystem        node|python|rust|go|ruby|java|unknown
  package_manager  npm|yarn|pnpm|bun|poetry|uv|pip|cargo|go|bundler|maven|gradle|null
  test/lint/build/dev/typecheck   command string, or null if absent
  syntax_check     template with {file}, for repos with no build step
  dev_port         int, or null. A conventional default for the detected
                   framework -- NOT read from config. Treat as a hint.
  has_test_runner  bool. False means "do not claim tests ran."
  notes            strings worth surfacing to the user
"""
import json
import os
import re
import sys

# Conventional dev-server ports by framework. These are defaults, not truth --
# a project can override any of them, so `dev_port` is only ever a hint.
FRAMEWORK_PORTS = [
    ("next", 3000), ("nuxt", 3000), ("@angular/core", 4200), ("astro", 4321),
    ("@sveltejs/kit", 5173), ("vite", 5173), ("react-scripts", 3000),
    ("@nestjs/core", 3000), ("express", 3000), ("fastify", 3000),
]
NPM_TEST_PLACEHOLDER = "no test specified"


def read(path):
    try:
        with open(path, encoding="utf-8") as fh:
            return fh.read()
    except (OSError, UnicodeDecodeError):
        return None


def load_json(path):
    raw = read(path)
    if raw is None:
        return None
    try:
        return json.loads(raw)
    except ValueError:
        return None


def result(**kw):
    out = {"ecosystem": "unknown", "package_manager": None, "test": None,
           "lint": None, "build": None, "dev": None, "typecheck": None,
           "syntax_check": None, "dev_port": None, "has_test_runner": False,
           "notes": []}
    out.update(kw)
    return out


def detect_node(root, notes):
    pkg = load_json(os.path.join(root, "package.json"))
    if pkg is None:
        notes.append("package.json is present but unparseable; treating stack as unknown.")
        return None

    lockfiles = [(f, m) for f, m in (("pnpm-lock.yaml", "pnpm"), ("yarn.lock", "yarn"),
                                     ("bun.lockb", "bun"), ("bun.lock", "bun"),
                                     ("package-lock.json", "npm"))
                 if os.path.exists(os.path.join(root, f))]
    if len(lockfiles) > 1:
        notes.append("Multiple lockfiles (%s) -- tools may resolve different versions."
                     % ", ".join(f for f, _ in lockfiles))
    pm = lockfiles[0][1] if lockfiles else "npm"
    run = "%s run" % pm if pm != "npm" else "npm run"

    scripts = pkg.get("scripts") or {}

    def script(*names):
        for n in names:
            if n in scripts:
                return "%s %s" % (run, n)
        return None

    test = None
    if "test" in scripts:
        if NPM_TEST_PLACEHOLDER in scripts["test"]:
            notes.append("`test` script is the npm placeholder -- there is no real test runner.")
        else:
            test = "%s test" % pm if pm != "npm" else "npm test"

    deps = {}
    for key in ("dependencies", "devDependencies", "peerDependencies"):
        deps.update(pkg.get(key) or {})

    if test is None:
        for runner in ("vitest", "jest", "mocha", "ava", "@playwright/test", "node:test"):
            if runner in deps:
                notes.append("`%s` is installed but no `test` script is defined." % runner)
                break

    port = next((p for name, p in FRAMEWORK_PORTS if name in deps), None)

    if pkg.get("workspaces"):
        notes.append("Workspaces detected -- per-package commands may differ from the root.")

    return result(
        ecosystem="node", package_manager=pm, test=test,
        lint=script("lint", "eslint"), build=script("build"),
        dev=script("dev", "start", "serve"),
        typecheck=script("typecheck", "type-check", "tsc"),
        syntax_check="node --check {file}", dev_port=port,
        has_test_runner=test is not None, notes=notes,
    )


def detect_python(root, notes):
    pyproject = read(os.path.join(root, "pyproject.toml")) or ""
    has_poetry = "[tool.poetry]" in pyproject
    has_uv = os.path.exists(os.path.join(root, "uv.lock"))
    pm = "uv" if has_uv else "poetry" if has_poetry else "pip"
    prefix = {"uv": "uv run ", "poetry": "poetry run ", "pip": ""}[pm]

    reqs = " ".join(filter(None, [
        pyproject,
        read(os.path.join(root, "requirements.txt")) or "",
        read(os.path.join(root, "requirements-dev.txt")) or "",
    ]))

    has_pytest = "pytest" in reqs or os.path.exists(os.path.join(root, "pytest.ini"))
    has_tests_dir = os.path.isdir(os.path.join(root, "tests"))
    if has_tests_dir and not has_pytest:
        notes.append("A tests/ directory exists but no pytest config -- confirm the runner.")

    lint = None
    for tool in ("ruff", "flake8", "pylint"):
        if tool in reqs:
            lint = "%s%s check ." % (prefix, tool) if tool == "ruff" else "%s%s ." % (prefix, tool)
            break

    return result(
        ecosystem="python", package_manager=pm,
        test="%spytest" % prefix if has_pytest else None,
        lint=lint,
        typecheck="%smypy ." % prefix if "mypy" in reqs else None,
        syntax_check="python -m py_compile {file}",
        has_test_runner=has_pytest, notes=notes,
    )


def detect_rust(root, notes):
    return result(ecosystem="rust", package_manager="cargo", test="cargo test",
                  lint="cargo clippy -- -D warnings", build="cargo build",
                  syntax_check="cargo check", has_test_runner=True, notes=notes)


def detect_go(root, notes):
    return result(ecosystem="go", package_manager="go", test="go test ./...",
                  lint="go vet ./...", build="go build ./...",
                  syntax_check="go build ./...", has_test_runner=True, notes=notes)


def detect_ruby(root, notes):
    gemfile = read(os.path.join(root, "Gemfile")) or ""
    test = None
    if "rspec" in gemfile:
        test = "bundle exec rspec"
    elif "minitest" in gemfile or os.path.isdir(os.path.join(root, "test")):
        test = "bundle exec rake test"
    return result(ecosystem="ruby", package_manager="bundler", test=test,
                  lint="bundle exec rubocop" if "rubocop" in gemfile else None,
                  syntax_check="ruby -c {file}",
                  has_test_runner=test is not None, notes=notes)


def detect_java(root, notes):
    if os.path.exists(os.path.join(root, "pom.xml")):
        return result(ecosystem="java", package_manager="maven", test="mvn test",
                      build="mvn -q compile", has_test_runner=True, notes=notes)
    wrapper = "./gradlew" if os.path.exists(os.path.join(root, "gradlew")) else "gradle"
    return result(ecosystem="java", package_manager="gradle", test="%s test" % wrapper,
                  build="%s build" % wrapper, has_test_runner=True, notes=notes)


# Ordered: the first marker found wins. package.json is last among the
# ambiguous ones so a Python or Go service with a package.json for tooling
# isn't misread as a Node project.
MARKERS = [
    ("Cargo.toml", detect_rust),
    ("go.mod", detect_go),
    ("pom.xml", detect_java),
    ("build.gradle", detect_java),
    ("build.gradle.kts", detect_java),
    ("Gemfile", detect_ruby),
    ("pyproject.toml", detect_python),
    ("setup.py", detect_python),
    ("requirements.txt", detect_python),
    ("package.json", detect_node),
]


def detect(root):
    notes = []
    found = [(m, fn) for m, fn in MARKERS if os.path.exists(os.path.join(root, m))]
    if not found:
        notes.append("No recognized project manifest in %s -- ask the user for the "
                     "test, lint, and build commands." % root)
        return result(notes=notes)

    if len(found) > 1:
        others = ", ".join(m for m, _ in found[1:])
        notes.append("Multiple manifests present (also: %s); reporting %s."
                     % (others, found[0][0]))

    out = found[0][1](root, notes)
    return out if out is not None else result(notes=notes)


def main():
    root = os.path.abspath(sys.argv[1] if len(sys.argv) > 1 else ".")
    out = detect(root)
    if not out["has_test_runner"]:
        out["notes"].append(
            "No test runner detected. Do not claim tests passed -- report exactly "
            "which checks ran, and treat the user's manual check as the real evidence.")
    out["root"] = root
    print(json.dumps(out, indent=2))


if __name__ == "__main__":
    main()
