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