from sqlalchemy import select

from app.models import Document, DocumentChunk


def test_upload_document(client, db_session):
    response = client.post(
        "/documents/upload",
        data={
            "service_name": "checkout-api",
            "document_type": "runbook",
            "severity": "high",
        },
        files={
            "file": (
                "checkout-runbook.md",
                (
                    b"# Checkout Runbook\n\n"
                    b"Check payment provider latency and database connection pool usage."
                ),
                "text/markdown",
            )
        },
    )

    assert response.status_code == 201

    data = response.json()

    assert data["filename"] == "checkout-runbook.md"
    assert data["content_type"] == "text/markdown"
    assert data["service_name"] == "checkout-api"
    assert data["document_type"] == "runbook"
    assert data["severity"] == "high"
    assert data["chunk_count"] >= 1

    document = db_session.get(Document, data["id"])

    assert document is not None
    assert "payment provider latency" in document.content


def test_upload_document_rejects_binary_file(client):
    response = client.post(
        "/documents/upload",
        data={
            "service_name": "checkout-api",
            "document_type": "runbook",
        },
        files={
            "file": (
                "binary-file.bin",
                b"\xff\xfe\x00\x00",
                "application/octet-stream",
            )
        },
    )

    assert response.status_code == 400
    assert "Only UTF-8 text documents" in response.json()["detail"]


def test_index_documents(client, db_session):
    document = Document(
        title="Manual Database Runbook",
        filename="database-runbook.md",
        content_type="text/markdown",
        service_name="payments-api",
        document_type="runbook",
        severity="high",
        content=(
            "Database connection pool exhaustion can cause checkout latency. "
            "Check slow queries and active connections."
        ),
    )

    db_session.add(document)
    db_session.commit()

    response = client.post("/documents/index")

    assert response.status_code == 200

    data = response.json()

    assert data["documents_indexed"] == 1
    assert data["chunks_created"] >= 1

    statement = select(DocumentChunk).where(
        DocumentChunk.document_id == document.id
    )

    chunks = db_session.execute(statement).scalars().all()

    assert len(chunks) >= 1


def test_retrieve(client):
    unique_term = "incidentpilotneedle123"

    upload_response = client.post(
        "/documents/upload",
        data={
            "service_name": "payments-api",
            "document_type": "runbook",
            "severity": "high",
        },
        files={
            "file": (
                "needle-runbook.md",
                (
                    f"# Needle Runbook\n\n"
                    f"When debugging {unique_term}, check payment timeout "
                    f"logs and provider status."
                ).encode("utf-8"),
                "text/markdown",
            )
        },
    )

    assert upload_response.status_code == 201

    retrieve_response = client.post(
        "/retrieve",
        json={
            "query": unique_term,
            "service_name": "payments-api",
            "top_k": 3,
        },
    )

    assert retrieve_response.status_code == 200

    chunks = retrieve_response.json()["chunks"]

    assert len(chunks) >= 1

    combined_content = " ".join(
        chunk["content"]
        for chunk in chunks
    ).lower()

    assert unique_term in combined_content
    assert chunks[0]["metadata"]["service_name"] == "payments-api"
    assert "score" in chunks[0]


def test_retrieve_filters_by_service_name(client):
    shared_text = "database timeout after deployment caused payment failures"

    client.post(
        "/documents/upload",
        data={
            "service_name": "payments-api",
            "document_type": "runbook",
            "severity": "high",
        },
        files={
            "file": (
                "payments-runbook.md",
                shared_text.encode("utf-8"),
                "text/markdown",
            )
        },
    )

    client.post(
        "/documents/upload",
        data={
            "service_name": "search-api",
            "document_type": "runbook",
            "severity": "medium",
        },
        files={
            "file": (
                "search-runbook.md",
                shared_text.encode("utf-8"),
                "text/markdown",
            )
        },
    )

    response = client.post(
        "/retrieve",
        json={
            "query": "database timeout after deployment",
            "service_name": "payments-api",
            "top_k": 5,
        },
    )

    assert response.status_code == 200

    chunks = response.json()["chunks"]

    assert len(chunks) >= 1

    assert all(
        chunk["metadata"]["service_name"] == "payments-api"
        for chunk in chunks
    )
