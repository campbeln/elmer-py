#!/bin/bash
# Browser test runner: starts the stub Supabase and the Elmer server, runs
# the three jsdom harnesses, and tears everything down by PID (never pkill —
# a pkill pattern can match the invoking shell's own command line).
#
# Usage, from tests/browser/:
#   npm install     # once
#   npm test        # or: bash run.sh
set -u
cd "$(dirname "$0")"
ROOT="$(cd ../.. && pwd)"

export TICKETS_ADMIN_KEY="${TICKETS_ADMIN_KEY:-test-admin-key}"
export ELMER_ADMIN_KEY="${ELMER_ADMIN_KEY:-test-elmer-ops-key}"
export SUPABASE_URL="http://127.0.0.1:9999"
export SUPABASE_SERVICE_KEY="stub"

if [ ! -d node_modules ]; then
    echo "node_modules missing — run 'npm install' in tests/browser first."
    exit 2
fi

python3 stub_supabase.py > /tmp/elmer-test-stub.log 2>&1 &
STUB_PID=$!
# `exec` replaces this subshell's process image with python3's, so $!
# captures python3's own PID rather than a subshell wrapping it — without
# this, `kill $SERVER_PID` on exit can silently fail to stop the actual
# server, leaving an orphan that keeps listening on :3001 and keeps
# accumulating in-process rate-limit state across every later test run
# (this happened for real during development: a stray server survived
# from one run.sh invocation to the next and started 429-ing all of them).
(cd "$ROOT" && exec python3 _index.py dev > /tmp/elmer-test-server.log 2>&1) &
SERVER_PID=$!
trap 'kill $STUB_PID $SERVER_PID 2>/dev/null' EXIT

# Wait for the server to come up (max ~10s).
for i in $(seq 1 20); do
    if curl -s -o /dev/null --max-time 1 http://127.0.0.1:3001/; then break; fi
    sleep 0.5
done

FAILED=0
for t in test_queue.js test_view_and_status.js test_submit_form.js test_ambient_key.js test_public_view.js test_session_cookie.js test_reporter_message.js test_responsive_css.js; do
    echo "============================================================"
    echo "$t"
    echo "============================================================"
    node "$t" || FAILED=1
done

echo "============================================================"
if [ "$FAILED" -eq 0 ]; then echo "BROWSER SUITE: PASS"; else echo "BROWSER SUITE: FAIL"; fi
exit $FAILED
