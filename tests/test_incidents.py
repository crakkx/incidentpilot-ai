from sqlalchemy import select

from app.models import Incident, Service


def test_create_incident(client, db_session):
    response = client.post(
        "/incidents",
        json={
            "title": "Payments timeout during checkout",
            "severity": "high",
            "description": "Users cannot complete payment.",
            "service_name": "payments-api",
        },
    )

    assert response.status_code == 201

    data = response.json()

    assert data["title"] == "Payments timeout during checkout"
    assert data["severity"] == "high"
    assert data["status"] == "open"
    assert data["service_name"] == "payments-api"

    incident = db_session.get(Incident, data["id"])

    assert incident is not None
    assert incident.title == "Payments timeout during checkout"
    assert incident.service_name == "payments-api"


def test_list_incidents(client):
    client.post(
        "/incidents",
        json={
            "title": "Checkout latency spike",
            "severity": "medium",
            "service_name": "checkout-api",
        },
    )

    client.post(
        "/incidents",
        json={
            "title": "Search API errors",
            "severity": "low",
            "service_name": "search-api",
        },
    )

    response = client.get("/incidents")

    assert response.status_code == 200

    incidents = response.json()

    titles = {
        incident["title"]
        for incident in incidents
    }

    assert "Checkout latency spike" in titles
    assert "Search API errors" in titles


def test_create_incident_normalizes_service_name(client, db_session):
    response = client.post(
        "/incidents",
        json={
            "title": "Checkout is slow",
            "severity": "high",
            "service_name": " Checkout-API ",
        },
    )

    assert response.status_code == 201
    assert response.json()["service_name"] == "checkout-api"

    statement = select(Service).where(Service.name == "checkout-api")
    service = db_session.execute(statement).scalar_one_or_none()

    assert service is not None
