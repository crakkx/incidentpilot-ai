import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.append(str(PROJECT_ROOT))

from app import models  # noqa: E402
from app.db.session import SessionLocal, init_db  # noqa: E402
from app.services.retrieval_service import index_document  # noqa: E402


RUNBOOKS = [
    {
        "title": "Checkout Latency Runbook",
        "filename": "checkout-latency-runbook.md",
        "content_type": "text/markdown",
        "content": """
# Checkout Latency Runbook

Use this runbook when checkout-api latency increases or users report slow checkout.

First checks:
- Check recent checkout-api deployments.
- Check payment provider latency.
- Check database connection pool usage.
- Search checkout-api logs for WARN and ERROR messages.
- Compare latency before and after the latest deployment.

Common causes:
- Payment provider timeout.
- Database connection pool saturation.
- Slow inventory reservation.
- Bad deployment introducing extra network calls.

Useful actions:
- Roll back the latest checkout-api deployment if errors started after deploy.
- Increase payment timeout only after confirming provider health.
- Escalate to the commerce-platform team if checkout failures affect many users.
""",
    },
    {
        "title": "Payment Timeout Runbook",
        "filename": "payment-timeout-runbook.md",
        "content_type": "text/markdown",
        "content": """
# Payment Timeout Runbook

Use this runbook when payments-api reports authorization failures or upstream timeouts.

First checks:
- Check payment provider status page.
- Check timeout errors in payments-api logs.
- Check retry queue depth.
- Check fraud service latency.
- Check whether failures are isolated to one provider.

Common causes:
- External payment provider degradation.
- Retry queue backlog.
- Network timeout between payments-api and provider.
- Fraud scoring dependency latency.

Useful actions:
- Enable fallback provider if available.
- Reduce traffic to the failing provider.
- Alert the payments-team.
- Inspect ERROR logs with status code 504.
""",
    },
    {
        "title": "Database Connection Pool Runbook",
        "filename": "database-connection-pool-runbook.md",
        "content_type": "text/markdown",
        "content": """
# Database Connection Pool Runbook

Use this runbook when services report slow database queries or connection pool exhaustion.

First checks:
- Check database connection pool usage.
- Check number of active database connections.
- Look for slow queries.
- Compare traffic volume to normal baseline.
- Check whether a new deployment changed query behavior.

Common causes:
- Connection leak.
- Too many concurrent requests.
- Slow query locking tables.
- Missing database index.
- New deployment causing inefficient query patterns.

Useful actions:
- Restart affected service only if there is a confirmed connection leak.
- Roll back recent deployment if query behavior changed.
- Add temporary rate limiting if traffic spike is causing exhaustion.
""",
    },
    {
        "title": "Deployment Rollback Runbook",
        "filename": "deployment-rollback-runbook.md",
        "content_type": "text/markdown",
        "content": """
# Deployment Rollback Runbook

Use this runbook when an incident starts shortly after a deployment.

First checks:
- Identify the most recent deployment for the affected service.
- Compare error rate before and after deployment.
- Check logs for new exception messages.
- Check whether only the deployed service is affected.
- Confirm whether dependent services also changed.

Rollback guidance:
- Roll back if customer impact is high and the deployment is strongly correlated with the incident.
- Notify the owning team before rollback when possible.
- After rollback, confirm error rate and latency return to baseline.

Useful evidence:
- Deployment timestamp.
- Commit SHA.
- Error rate chart.
- Service logs.
""",
    },
    {
        "title": "Search API Latency Runbook",
        "filename": "search-api-latency-runbook.md",
        "content_type": "text/markdown",
        "content": """
# Search API Latency Runbook

Use this runbook when search-api latency increases or product search results load slowly.

First checks:
- Check search backend latency.
- Check cache hit rate.
- Check query volume.
- Check recent search-api deployments.
- Look for timeout errors in search-api logs.

Common causes:
- Cache miss spike.
- Search index degradation.
- Expensive query pattern.
- Recent deployment changing ranking logic.

Useful actions:
- Enable degraded mode if search backend is overloaded.
- Increase cache TTL temporarily.
- Roll back recent ranking changes if latency started after deployment.
""",
    },
]


def main():
    init_db()

    db = SessionLocal()

    try:
        documents_created = 0
        chunks_created = 0

        for runbook in RUNBOOKS:
            document = (
                db.query(models.Document)
                .filter(models.Document.title == runbook["title"])
                .first()
            )

            if document is None:
                document = models.Document(
                    title=runbook["title"],
                    filename=runbook["filename"],
                    content_type=runbook["content_type"],
                    content=runbook["content"].strip(),
                )

                db.add(document)
                db.flush()
                documents_created += 1

            created_for_document = index_document(db, document)
            chunks_created += created_for_document

        db.commit()

        print(f"Documents created: {documents_created}")
        print(f"Chunks created: {chunks_created}")

    finally:
        db.close()


if __name__ == "__main__":
    main()
