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