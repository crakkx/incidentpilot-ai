#!/bin/sh

set -eu

PROJECT_ROOT=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
cd "$PROJECT_ROOT"

API_URL="${API_URL:-http://localhost:8000}"
OLLAMA_URL="${OLLAMA_URL:-http://localhost:11434}"
REPORT_PATH="reports/demo_rca.json"

echo "============================================================"
echo "IncidentPilot AI — End-to-End RCA Demo"
echo "============================================================"
echo

echo "1. Checking Ollama..."
if ! curl -fsS "$OLLAMA_URL/api/tags" >/dev/null; then
    echo "Ollama is not reachable at $OLLAMA_URL."
    echo "Start the Ollama application and try again."
    exit 1
fi

echo "   Ollama is reachable."
echo

echo "2. Starting Docker services..."
docker compose up -d

echo
echo "3. Waiting for the API..."

attempt=0

until curl -fsS "$API_URL/health" >/dev/null; do
    attempt=$((attempt + 1))

    if [ "$attempt" -ge 30 ]; then
        echo "API did not become ready."
        docker compose logs api
        exit 1
    fi

    sleep 2
done

echo "   API is healthy."
echo

echo "4. Applying migrations..."
docker compose exec -T api alembic upgrade head

echo
echo "5. Seeding incident evidence..."

SEED_OUTPUT=$(
    docker compose exec -T api \
        python scripts/seed_day9_rca.py
)

printf '%s\n' "$SEED_OUTPUT"

INCIDENT_ID=$(
    printf '%s\n' "$SEED_OUTPUT" |
        awk -F': ' '/Incident ID:/ {print $2}' |
        tail -n 1 |
        tr -d '\r'
)

if [ -z "$INCIDENT_ID" ]; then
    echo "Could not determine the seeded incident ID."
    exit 1
fi

echo
echo "6. Running RCA analysis with Qwen 2.5 3B..."
echo "   Incident ID: $INCIDENT_ID"

mkdir -p reports

HTTP_STATUS=$(
    curl -sS \
        -o "$REPORT_PATH" \
        -w "%{http_code}" \
        -X POST \
        "$API_URL/incidents/$INCIDENT_ID/analyze"
)

if [ "$HTTP_STATUS" != "201" ]; then
    echo
    echo "Analysis failed with HTTP status $HTTP_STATUS."
    cat "$REPORT_PATH"
    echo
    exit 1
fi

echo
echo "7. Structured RCA report:"
echo

docker compose exec -T api \
    python -m json.tool /app/reports/demo_rca.json

echo
echo "============================================================"
echo "Demo completed successfully."
echo "Saved report: $REPORT_PATH"
echo "API documentation: $API_URL/docs"
echo "============================================================"
