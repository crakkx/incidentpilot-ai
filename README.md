# IncidentPilot AI

IncidentPilot AI is an AI-powered incident analysis assistant.

The goal is to help engineers investigate software incidents by combining service metadata, logs, deployments, runbooks, documents, retrieval, and AI analysis.

## Current Status

Day 1 foundation complete:

- FastAPI backend
- Postgres service
- Redis service
- Docker Compose setup
- `/health` endpoint
- GitHub Actions CI
- Basic test coverage

## Day 2 Endpoints

### `POST /incidents`

Creates a new incident.

### `GET /incidents`

Lists incidents.

### `POST /documents/upload`

Uploads a UTF-8 text document such as a runbook.

### `POST /logs/ingest`

Ingests service logs for later analysis.

- SQLAlchemy database models
- Incident, service, log, deployment, document, and analysis run tables
- Seed script
- Synthetic log generator
- Incident, document upload, and log ingestion APIs


## Day 3: Retrieval Foundation

Day 3 adds the first retrieval system.

### New pieces

- Basic document chunking
- Local hash-based embeddings
- pgvector support in Postgres
- `document_chunks` table
- Retrieval endpoint
- Synthetic runbook Q&A evals
- Architecture diagram

### New endpoints

#### `POST /documents/index`

Indexes existing documents by splitting them into chunks and storing embeddings.

#### `POST /retrieve`

Retrieves relevant document chunks for a user query.

Example:

```bash
curl -X POST http://localhost:8000/retrieve \
  -H "Content-Type: application/json" \
  -d '{
    "query": "What should I check if checkout latency increases?",
    "top_k": 3
  }'


## Tech Stack

- Python
- FastAPI
- Postgres
- Redis
- Docker Compose
- GitHub Actions

## Local Development

### Start the full stack

```bash
docker compose up --build
```

<!-- RETRIEVAL_EVAL_START -->
## Current retrieval evaluation

Last evaluated: `2026-07-14T17:46:16.803562+00:00`

Embedding model: `sentence-transformers/all-MiniLM-L6-v2`

| Metric | Current result |
|---|---:|
| Hit@1 | 90.00% |
| Hit@3 | 100.00% |
| Hit@5 | 100.00% |
| MRR | 0.9500 |
| Average latency | 31.20 ms |
| Evaluation queries | 10 |

The evaluation uses seeded IncidentPilot runbooks with metadata and
keyword-based relevance labels. Detailed results are written to
`reports/retrieval_eval_latest.json`.
<!-- RETRIEVAL_EVAL_END -->
