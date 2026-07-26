#!/usr/bin/env bash
# Start a project's dev server and wait for its port to answer.
#
# Usage: start-dev.sh [project-dir] [port]
#   project-dir  defaults to cwd
#   port         overrides the detected default (detection is a hint, not truth)
#
# The dev command and a conventional port come from detect-stack.py, so this
# works on any project it recognizes rather than hardcoding one repo's setup.
# For a project with separate backend and frontend, call it once per directory
# -- backend first, since the frontend calls it.
#
# Idempotent: a port already serving is left alone.
# Exit 0 = up. Exit 1 = failed to start (log tail printed). Exit 2 = usage.
set -uo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
DIR="${1:-$PWD}"
PORT_OVERRIDE="${2:-}"
LOG_DIR="${LOG_DIR:-${TMPDIR:-/tmp}}"

[ -d "$DIR" ] || { echo "start-dev: no such directory: $DIR" >&2; exit 2; }
DIR="$(cd "$DIR" && pwd)"
NAME="$(basename "$DIR")"
LOG="$LOG_DIR/dev-$NAME.log"

STACK="$(python3 "$HERE/detect-stack.py" "$DIR")" || {
  echo "start-dev: could not inspect $DIR" >&2; exit 1; }

field() { printf '%s' "$STACK" | python3 -c "
import json,sys
v = json.load(sys.stdin).get('$1')
print('' if v is None else v)"; }

CMD="$(field dev)"
PORT="${PORT_OVERRIDE:-$(field dev_port)}"

if [ -z "$CMD" ]; then
  echo "  $NAME: no dev command found in this project."
  echo "  Ask the user how to start it, or pass the command directly."
  exit 1
fi

up() { nc -z localhost "$1" >/dev/null 2>&1; }

if [ -n "$PORT" ] && up "$PORT"; then
  echo "  $NAME already running on http://localhost:$PORT (left alone)"
  exit 0
fi

echo "  $NAME: starting \`$CMD\`"
( cd "$DIR" && nohup sh -c "$CMD" >"$LOG" 2>&1 & )

if [ -z "$PORT" ]; then
  # No conventional port for this framework -- can't poll, so don't claim it's up.
  sleep 3
  echo "  $NAME started; no known port to poll. Check the log: $LOG"
  exit 0
fi

for _ in $(seq 1 40); do          # ~20s
  up "$PORT" && { echo "  $NAME is up on http://localhost:$PORT"; exit 0; }
  sleep 0.5
done

echo "  $NAME did NOT come up on port $PORT. Last log lines:"
tail -n 15 "$LOG" 2>/dev/null | sed 's/^/    /'
echo "  (port was a conventional default for the detected framework -- if the"
echo "   project uses a different one, pass it: start-dev.sh \"$DIR\" <port>)"
exit 1
