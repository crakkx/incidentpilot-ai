def test_create_placeholder_analysis(client):
    incident_response = client.post(
        "/incidents",
        json={
            "title": "Checkout failure",
            "severity": "high",
            "service_name": "checkout-api",
        },
    )

    assert incident_response.status_code == 201

    incident_id = incident_response.json()["id"]

    response = client.post(
        "/analysis",
        json={
            "incident_id": incident_id,
            "question": "What happened?",
        },
    )

    assert response.status_code == 201

    data = response.json()

    assert data["incident_id"] == incident_id
    assert data["status"] == "pending"
    assert "LLM analysis is not implemented yet" in data["summary"]


def test_analysis_rejects_missing_incident(client):
    response = client.post(
        "/analysis",
        json={
            "incident_id": "missing-incident-id",
            "question": "What happened?",
        },
    )

    assert response.status_code == 404
    assert response.json()["detail"] == "incident not found"
