from fastapi.testclient import TestClient

from app.main import app


def test_document_upload_creates_chunks_and_retrieval_works():
    unique_term = "incidentpilotneedle123"

    with TestClient(app) as client:
        upload_response = client.post(
            "/documents/upload",
            files={
                "file": (
                    "needle-runbook.md",
                    (
                        f"# Needle Runbook\n\n"
                        f"When debugging {unique_term}, check the special "
                        f"payment timeout guide and provider logs."
                    ).encode("utf-8"),
                    "text/markdown",
                )
            },
        )

        assert upload_response.status_code == 201

        uploaded = upload_response.json()

        assert uploaded["chunk_count"] >= 1

        retrieve_response = client.post(
            "/retrieve",
            json={
                "query": unique_term,
                "top_k": 3,
            },
        )

        assert retrieve_response.status_code == 200

        results = retrieve_response.json()["results"]

        assert len(results) >= 1

        combined_content = " ".join(
            result["content"]
            for result in results
        ).lower()

        assert unique_term in combined_content
