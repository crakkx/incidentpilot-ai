# IncidentPilot AI

IncidentPilot AI is a local-first incident investigation and root-cause
analysis backend.

It combines incident data, application logs, deployments, service metrics,
runbook retrieval, and a local LLM to generate a structured RCA report with
traceable evidence.

The project runs without a paid model API. RCA generation uses
`qwen2.5:3b` through Ollama on Apple Silicon.

---

## What problem does this solve?

Production incidents usually require engineers to manually inspect several
separate data sources:

- incident descriptions;
- application logs;
- recent deployments;
- service metrics;
- operational runbooks.

This slows down the initial investigation and makes it easy to miss useful
evidence.

IncidentPilot AI collects the relevant evidence for a specific incident,
retrieves matching runbook sections, and sends the prepared context to a local
LLM. The LLM returns a validated and structured RCA report rather than
uncontrolled free-form text.

The system is designed to assist an engineer, not replace final human
judgment.

---

## Main capabilities

- Create and list incidents
- Ingest service logs
- Store service deployments and metrics
- Upload and chunk operational documents
- Generate real text embeddings with Sentence Transformers
- Store and search vectors using PostgreSQL and pgvector
- Filter retrieval by service, document type, and severity
- Evaluate retrieval using Hit@1, Hit@3, Hit@5, MRR, and latency
- Collect incident evidence using fixed time windows
- Generate local RCA reports with Qwen 2.5 3B
- Validate LLM output using strict Pydantic schemas
- Reject fabricated evidence IDs
- Save completed and failed analysis runs for auditing
- Run isolated database tests in CI

---

## Architecture

~~~mermaid
flowchart LR
    User[User or API Client] --> FastAPI[FastAPI Backend]

    FastAPI --> IncidentService[Incident Service]
    FastAPI --> RCAService[RCA Analysis Service]
    FastAPI --> RetrievalService[Retrieval Service]

    IncidentService --> PostgreSQL[(PostgreSQL)]

    RCAService --> EvidenceCollector[Evidence Collector]
    EvidenceCollector --> Logs[(Logs)]
    EvidenceCollector --> Deployments[(Deployments)]
    EvidenceCollector --> Metrics[(Metrics)]
    EvidenceCollector --> RetrievalService

    RetrievalService --> EmbeddingModel[
        Sentence Transformers
        all-MiniLM-L6-v2
    ]

    RetrievalService --> PGVector[
        PostgreSQL + pgvector
    ]

    RCAService --> Ollama[
        Ollama on macOS
    ]

    Ollama --> Qwen[
        Qwen 2.5 3B
    ]

    Qwen --> Validation[
        Pydantic Validation
        and Evidence-ID Checks
    ]

    Validation --> AnalysisRuns[
        analysis_runs table
    ]
~~~

### RCA request flow

~~~text
POST /incidents/{incident_id}/analyze
        ↓
Load incident
        ↓
Collect logs: incident start ± 30 minutes
        ↓
Collect metrics: incident start ± 30 minutes
        ↓
Collect deployments: -2 hours to +30 minutes
        ↓
Retrieve top 5 matching runbook chunks
        ↓
Send structured evidence to Qwen 2.5 3B
        ↓
Validate JSON with Pydantic
        ↓
Verify every cited evidence ID
        ↓
Save report and evidence snapshot
~~~

A deliberate design choice is that the LLM does not directly query the
database. Python performs deterministic evidence collection, while the model
only interprets the evidence supplied to it.

---

## Tech stack

| Area | Technology |
|---|---|
| API | FastAPI |
| Validation | Pydantic |
| ORM | SQLAlchemy 2.x |
| Database | PostgreSQL |
| Vector search | pgvector |
| Database migrations | Alembic |
| Embeddings | `sentence-transformers/all-MiniLM-L6-v2` |
| Local LLM runtime | Ollama |
| RCA model | `qwen2.5:3b` |
| Cache / future jobs | Redis |
| Containers | Docker and Docker Compose |
| Testing | pytest and FastAPI TestClient |
| CI | GitHub Actions |

---

## Project structure

~~~text
incidentpilot-ai/
├── app/
│   ├── api/routes/          # FastAPI endpoints
│   ├── core/                # Configuration and logging
│   ├── db/                  # SQLAlchemy sessions and model registry
│   ├── evals/               # Retrieval evaluation implementation
│   ├── llm/                 # Ollama client and prompts
│   ├── models/              # SQLAlchemy database models
│   ├── rag/                 # Chunking, embeddings, vector retrieval
│   ├── repositories/        # Database query layer
│   ├── schemas/             # Pydantic request and response models
│   └── services/            # Application business logic
├── alembic/                 # Database migrations
├── data/                    # Evaluation data
├── reports/                 # Generated evaluation reports
├── scripts/                 # Seed, demo, and reindex scripts
├── tests/                   # Isolated automated tests
├── docker-compose.yml
├── Dockerfile
├── Makefile
└── README.md
~~~

---

## Requirements

Install these before running the project:

- Docker Desktop
- Ollama
- Git
- `make`
- `curl`

The project was developed on an Apple Silicon Mac using Python 3.11 inside
Docker.

---

## Run locally from a clean clone

### 1. Clone the repository

~~~bash
git clone https://github.com/crakkx/incidentpilot-ai.git
cd incidentpilot-ai
~~~

### 2. Create the local environment file

~~~bash
cp .env.example .env
~~~

The committed `.env.example` contains development defaults. Real `.env` files
are not committed.

### 3. Start Ollama

Open the Ollama application, then ensure the model exists:

~~~bash
ollama pull qwen2.5:3b
~~~

Check that Ollama is reachable:

~~~bash
curl http://localhost:11434/api/tags
~~~

### 4. Perform one-time setup

~~~bash
make setup
~~~

This command:

- downloads/builds the API image;
- starts PostgreSQL, Redis, and FastAPI;
- applies development database migrations;
- creates and migrates the isolated test database;
- downloads Qwen only when it is not already installed.

The initial Docker build can take time. Normal code changes do not require
another rebuild.

### 5. Seed sample data

~~~bash
make seed
~~~

### 6. Run the end-to-end demo

~~~bash
make demo
~~~

The generated RCA is saved to:

~~~text
reports/demo_rca.json
~~~

Interactive API documentation is available at:

~~~text
http://localhost:8000/docs
~~~

---

## Common development commands

| Command | Purpose |
|---|---|
| `make up` | Start existing containers without rebuilding |
| `make down` | Stop containers without deleting data or model caches |
| `make migrate` | Apply development database migrations |
| `make seed` | Insert sample incidents, logs, metrics, deployments, and runbooks |
| `make reindex` | Rebuild document chunks and embeddings |
| `make test` | Run tests against the isolated test database |
| `make eval` | Run retrieval evaluation and update this README |
| `make demo` | Run the complete RCA demo |
| `make logs` | Follow FastAPI logs |
| `make status` | Show Docker and Ollama status |

Do not routinely run:

~~~bash
docker compose down -v
~~~

The `-v` option deletes PostgreSQL data and persistent model caches.

---

## API endpoints

| Method | Endpoint | Purpose |
|---|---|---|
| `GET` | `/health` | Service health check |
| `POST` | `/incidents` | Create an incident |
| `GET` | `/incidents` | List incidents |
| `POST` | `/logs/ingest` | Ingest service logs |
| `POST` | `/documents/upload` | Upload and index a text document |
| `POST` | `/documents/index` | Index documents that do not have chunks |
| `POST` | `/documents/reindex` | Rebuild all chunks and embeddings |
| `POST` | `/retrieve` | Retrieve scored runbook chunks |
| `POST` | `/incidents/{incident_id}/analyze` | Generate and save an RCA report |

---

## Example incident

~~~json
{
  "title": "Payments database timeout after deployment",
  "description": "Payment requests began failing shortly after a payments-api deployment. Application logs show database connection timeouts.",
  "severity": "high",
  "service_name": "payments-api"
}
~~~

The demo data includes:

- a payments-api deployment shortly before the incident;
- database timeout and connection-pool exhaustion logs;
- elevated error-rate, latency, and database-connection metrics;
- a matching database timeout runbook.

---

## Example RCA report

Representative structured output, shortened for readability:

~~~json
{
  "status": "completed",
  "model_name": "qwen2.5:3b",
  "report": {
    "incident_summary": "Payment requests failed after database connection timeouts were observed in payments-api.",
    "likely_root_cause": "The immediate failure mechanism was database connection-pool exhaustion. The recent deployment is a possible trigger, but the causal link requires further verification.",
    "evidence": [
      {
        "source_type": "log",
        "source_id": "<log-id>",
        "excerpt": "database connection timeout while authorizing payment",
        "explanation": "The authorization request directly failed while waiting for a database connection."
      },
      {
        "source_type": "log",
        "source_id": "<log-id>",
        "excerpt": "database connection pool exhausted; request failed",
        "explanation": "The application explicitly reported connection-pool exhaustion."
      },
      {
        "source_type": "metric",
        "source_id": "<metric-id>",
        "excerpt": "db_connections: 95 count",
        "explanation": "Database connection usage was elevated during the incident window."
      },
      {
        "source_type": "deployment",
        "source_id": "<deployment-id>",
        "excerpt": "payments-api v2.4.0 was deployed before the incident",
        "explanation": "The deployment is temporally correlated with the start of the failures."
      }
    ],
    "recommended_actions": [
      "Inspect the deployment for connection leaks and longer transactions.",
      "Review slow queries and database locks during the incident window.",
      "Roll back the deployment if connection usage and failures return to baseline afterward.",
      "Monitor payment error rate, latency, and database connections during mitigation."
    ],
    "confidence": "medium",
    "missing_information": [
      "Connection-pool limits and timeout configuration.",
      "Connection-usage trends immediately before and after deployment.",
      "Slow-query, lock, and distributed trace data.",
      "Whether rollback restores normal behavior."
    ]
  }
}
~~~

The exact wording varies because the report is generated locally by the model.
The response shape is fixed and validated by Pydantic.

---

<!-- RETRIEVAL_EVAL_START -->
## Current retrieval evaluation

Last evaluated: `2026-07-15T21:31:53.123235+00:00`

Embedding model: `sentence-transformers/all-MiniLM-L6-v2`

| Metric | Current result |
|---|---:|
| Hit@1 | 100.00% |
| Hit@3 | 100.00% |
| Hit@5 | 100.00% |
| MRR | 1.0000 |
| Average latency | 24.34 ms |
| Evaluation queries | 10 |

The evaluation uses seeded IncidentPilot runbooks with metadata and
keyword-based relevance labels. Detailed results are written to
`reports/retrieval_eval_latest.json`.
<!-- RETRIEVAL_EVAL_END -->

---

## Testing

Tests run against a separate PostgreSQL database named:

~~~text
incidentpilot_test
~~~

The test suite refuses to clean a database whose name does not contain
`test`.

Run all tests:

~~~bash
make test
~~~

The suite covers:

- health checks;
- incident creation and listing;
- log ingestion;
- document upload and indexing;
- real embedding generation;
- semantic retrieval and metadata filtering;
- retrieval metric calculations;
- seed scripts;
- structured RCA generation using a fake LLM client;
- analysis persistence;
- invalid model output;
- fabricated evidence IDs.

GitHub Actions runs migrations and the test suite automatically. CI does not
download or run Ollama because LLM calls are replaced with deterministic fake
clients.

---

## Retrieval evaluation

The retrieval evaluator uses a labeled set of incident questions and checks
where the first relevant chunk appears.

Metrics:

| Metric | Meaning |
|---|---|
| Hit@1 | Relevant chunk appears first |
| Hit@3 | Relevant chunk appears in the first three results |
| Hit@5 | Relevant chunk appears in the first five results |
| MRR | Rewards placing the first relevant result near the top |
| Average latency | End-to-end `/retrieve` response time |

Detailed results are generated at:

~~~text
reports/retrieval_eval_latest.json
reports/retrieval_eval_latest.md
~~~

---

## Current limitations

- Demo data is synthetic rather than connected to a real observability stack.
- Qwen 2.5 3B is lightweight enough for local use but can still make weak
  causal inferences.
- RCA generation is synchronous and can take several seconds.
- Retrieval uses dense vector search without hybrid keyword search or
  reranking.
- Evaluation relevance labels are based on expected metadata and keywords.
- There is no authentication or authorization layer yet.
- There is no frontend dashboard.
- Redis is provisioned but is not yet used for background jobs.
- The application has not yet been deployed to a public cloud environment.
- The system assists investigation but does not automatically execute
  remediation actions.

---

## Next steps

1. Move RCA generation to a background job using Redis.
2. Add analysis-run status and result endpoints.
3. Add hybrid dense and keyword retrieval.
4. Add a cross-encoder reranker.
5. Connect to real log, metric, deployment, and tracing systems.
6. Add OpenTelemetry traces and model latency/token metrics.
7. Add human feedback and RCA quality evaluation.
8. Add authentication and per-service access controls.
9. Build a small incident investigation dashboard.
10. Introduce LangGraph only when the system needs controlled multi-step tool
    execution.

---

## Engineering decisions

### Why local Ollama?

The project demonstrates an end-to-end LLM application without depending on a
paid API. It also keeps incident evidence on the local machine.

### Why no agent framework yet?

RCA v0 uses deterministic evidence collection. This makes data access,
failures, tests, and grounding easier to understand.

An agent framework becomes useful later when the model needs to repeatedly
select and execute tools.

### Why save the evidence snapshot?

Logs, metrics, and runbooks can change. Saving the exact evidence supplied to
the model makes each RCA run reproducible and auditable.

### Why validate evidence IDs?

Valid JSON does not guarantee grounded output. The application rejects reports
that cite log, metric, deployment, or runbook IDs that were not supplied to
the model.

---

## Project status

The current version contains the first complete AI flow:

~~~text
Incident
  → evidence collection
  → runbook retrieval
  → local LLM reasoning
  → structured validation
  → evidence verification
  → database persistence
~~~
