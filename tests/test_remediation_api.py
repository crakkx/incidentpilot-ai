from datetime import datetime
from uuid import uuid4
from fastapi.testclient import TestClient
from app.main import app
from app.models import AnalysisRun, Incident, Service

client = TestClient(app)

def test_remediation_approval_and_rejection_flow(db_session):
    suffix = uuid4().hex[:8]
    service = Service(name=f"svc-{suffix}", description="test svc")
    db_session.add(service)
    db_session.flush()

    incident = Incident(
        title="Test incident for remediation",
        description="Test description",
        severity="high",
        status="open",
        service_id=service.id,
        service_name=service.name,
        started_at=datetime.utcnow(),
    )
    db_session.add(incident)
    db_session.flush()

    proposal = {
        "incident_id": str(incident.id),
        "root_cause_summary": "High CPU caused by leak.",
        "actions": [
            {
                "action": "Restart container",
                "priority": "immediate",
                "target_entity": service.name,
                "rationale": "Clear memory leak.",
            }
        ],
        "confidence_level": "low",
        "status": "pending_approval",
        "proposed_at": datetime.utcnow().isoformat(),
    }

    run = AnalysisRun(
        incident_id=incident.id,
        status="awaiting_approval",
        progress_stage="awaiting_approval",
        progress_message="Awaiting approval",
        progress_percent=95,
        remediation_proposal=proposal,
    )
    db_session.add(run)
    db_session.commit()

    # GET proposal
    resp = client.get(f"/incidents/{incident.id}/remediation")
    assert resp.status_code == 200
    data = resp.json()
    assert data["confidence_level"] == "low"
    assert data["status"] == "pending_approval"

    # POST approve
    approve_resp = client.post(f"/incidents/{incident.id}/remediation/approve")
    assert approve_resp.status_code == 200
    assert approve_resp.json()["proposal"]["status"] == "approved"

    # Verify DB state updated
    db_session.refresh(run)
    assert run.status == "completed"


def test_remediation_rejection_flow(db_session):
    suffix = uuid4().hex[:8]
    service = Service(name=f"svc-{suffix}", description="test svc")
    db_session.add(service)
    db_session.flush()

    incident = Incident(
        title="Test incident for remediation reject",
        description="Test description",
        severity="high",
        status="open",
        service_id=service.id,
        service_name=service.name,
        started_at=datetime.utcnow(),
    )
    db_session.add(incident)
    db_session.flush()

    proposal = {
        "incident_id": str(incident.id),
        "root_cause_summary": "High CPU caused by leak.",
        "actions": [],
        "confidence_level": "low",
        "status": "pending_approval",
        "proposed_at": datetime.utcnow().isoformat(),
    }

    run = AnalysisRun(
        incident_id=incident.id,
        status="awaiting_approval",
        progress_stage="awaiting_approval",
        progress_message="Awaiting approval",
        progress_percent=95,
        remediation_proposal=proposal,
    )
    db_session.add(run)
    db_session.commit()

    # POST reject
    reject_resp = client.post(
        f"/incidents/{incident.id}/remediation/reject",
        json={"reason": "Incomplete actions"}
    )
    assert reject_resp.status_code == 200
    data = reject_resp.json()
    assert data["proposal"]["status"] == "rejected"
    assert data["proposal"]["rejection_reason"] == "Incomplete actions"

    # Verify DB state updated
    db_session.refresh(run)
    assert run.status == "rejected"
    assert run.progress_stage == "rejected"
