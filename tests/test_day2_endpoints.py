from fastapi.testclient import TestClient

from app.main import app


def test_create_and_list_incidents():
    with TestClient(app) as client:
        create_response = client.post(
            "/incidents",
            json={
                "title": "Checkout is slow",
                "severity": "high",
                "description": "Users report slow checkout.",
                "service_name": "checkout-api-test",
            },
        )

        assert create_response.status_code == 201

        created_incident = create_response.json()

        assert created_incident["title"] == "Checkout is slow"
        assert created_incident["severity"] == "high"
        assert created_incident["status"] == "open"

        list_response = client.get("/incidents")

        assert list_response.status_code == 200

        incidents = list_response.json()

        assert any(
            incident["id"] == created_incident["id"]
            for incident in incidents
        )


def test_ingest_logs():
    with TestClient(app) as client:
        response = client.post(
            "/logs/ingest",
            json={
                "service_name": "payments-api-test",
                "logs": [
                    {
                        "level": "INFO",
                        "message": "Payment request started",
                        "source": "test",
                    },
                    {
                        "level": "ERROR",
                        "message": "Payment provider timeout",
                        "source": "test",
                        "context": {"status_code": 504},
                    },
                ],
            },
        )

        assert response.status_code == 201

        result = response.json()

        assert result["ingested_count"] == 2
        assert result["service_name"] == "payments-api-test"
