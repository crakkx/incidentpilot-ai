#!/usr/bin/env bash
# Headless Locust run against a live IncidentPilot stack.
#
# Usage:
#   ./scripts/run_load_test.sh [host] [users] [spawn_rate] [duration]
#
# Defaults hit the local docker-compose stack with a light load. Requires
# the seeded operator account (make seed / scripts/seed_users.py) and
# `pip install -r requirements-load.txt`.
set -euo pipefail

HOST="${1:-http://localhost:8000}"
USERS="${2:-10}"
SPAWN_RATE="${3:-2}"
DURATION="${4:-1m}"

REPORT_DIR="reports/load"
mkdir -p "$REPORT_DIR"
TIMESTAMP="$(date +%Y%m%d_%H%M%S 2>/dev/null || echo run)"

echo "Running Locust: host=$HOST users=$USERS spawn_rate=$SPAWN_RATE duration=$DURATION"

locust \
  -f tests/load/locustfile.py \
  --host "$HOST" \
  --users "$USERS" \
  --spawn-rate "$SPAWN_RATE" \
  --run-time "$DURATION" \
  --headless \
  --print-stats \
  --html "$REPORT_DIR/report_$TIMESTAMP.html" \
  --csv "$REPORT_DIR/run_$TIMESTAMP"

echo "Report written to $REPORT_DIR/report_$TIMESTAMP.html"
