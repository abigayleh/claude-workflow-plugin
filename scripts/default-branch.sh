#!/usr/bin/env bash
# Print the repo's default/base branch, or exit non-zero if it can't be known.
#
# The usual one-liner (`git symbolic-ref refs/remotes/origin/HEAD`) fails on any
# repo without a remote. This walks from most authoritative to least, and
# refuses to guess when the answer is genuinely ambiguous. Callers treat a
# non-zero exit as "ask the user" -- never as "assume main".
#
# Exit 0 -> branch name on stdout.
# Exit 3 -> ambiguous; caller must ask the user. Space-separated candidates.
# Exit 1 -> no branches at all.
#
# Accepts an optional repo path so hooks can ask about a repo other than cwd.
#
# Kept POSIX-ish: macOS ships bash 3.2, so no mapfile and no empty-array reads.
set -uo pipefail

[ $# -gt 0 ] && cd "$1" 2>/dev/null

have_local() { git show-ref --verify --quiet "refs/heads/$1"; }

# 1. Set by clone. Cheap, offline, authoritative.
if b=$(git symbolic-ref --short refs/remotes/origin/HEAD 2>/dev/null); then
  echo "${b#origin/}"; exit 0
fi

# 2. Explicit local config, but only if that branch actually exists.
if b=$(git config --get init.defaultBranch 2>/dev/null) && [ -n "$b" ] && have_local "$b"; then
  echo "$b"; exit 0
fi

# 3. Ask the remote directly (network).
if git remote get-url origin >/dev/null 2>&1; then
  b=$(git ls-remote --symref origin HEAD 2>/dev/null \
      | awk '/^ref:/ { sub("refs/heads/", "", $2); print $2; exit }')
  if [ -n "${b:-}" ]; then echo "$b"; exit 0; fi
fi

# 4. Probe conventional names that exist locally. If more than one exists and
#    nothing above resolved it, this is a guess -- refuse rather than pick.
found=""
for b in main master trunk development; do
  have_local "$b" && found="$found $b"
done
found="${found# }"
count=$(printf '%s' "$found" | wc -w | tr -d ' ')

if [ "$count" -eq 1 ]; then
  echo "$found"; exit 0
elif [ "$count" -gt 1 ]; then
  echo "$found"; exit 3
fi

# 5. Nothing conventional. Use the sole branch if there's exactly one.
all=$(git for-each-ref --format='%(refname:short)' refs/heads/ 2>/dev/null | tr '\n' ' ')
all="${all%% }"
n=$(printf '%s' "$all" | wc -w | tr -d ' ')

if [ "$n" -eq 1 ]; then
  echo "${all% }"; exit 0
elif [ "$n" -gt 1 ]; then
  echo "$all"; exit 3
fi

exit 1
