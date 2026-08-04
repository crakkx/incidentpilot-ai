def test_login_success(anon_client, db_session):
    from app.core.security import hash_password
    from app.repositories.user_repository import create_user

    create_user(
        db_session,
        email="login-test@incidentpilot.example",
        hashed_password=hash_password("correct-password"),
        role="viewer",
    )
    db_session.commit()

    resp = anon_client.post(
        "/auth/login",
        json={"email": "login-test@incidentpilot.example", "password": "correct-password"},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["role"] == "viewer"
    assert body["access_token"]
    assert body["token_type"] == "bearer"


def test_login_wrong_password_rejected(anon_client, db_session):
    from app.core.security import hash_password
    from app.repositories.user_repository import create_user

    create_user(
        db_session,
        email="login-test-2@incidentpilot.example",
        hashed_password=hash_password("correct-password"),
        role="viewer",
    )
    db_session.commit()

    resp = anon_client.post(
        "/auth/login",
        json={"email": "login-test-2@incidentpilot.example", "password": "wrong-password"},
    )
    assert resp.status_code == 401


def test_login_unknown_email_rejected(anon_client):
    resp = anon_client.post(
        "/auth/login",
        json={"email": "nobody@incidentpilot.example", "password": "whatever"},
    )
    assert resp.status_code == 401


def test_unauthenticated_request_rejected(anon_client):
    resp = anon_client.get("/incidents")
    assert resp.status_code == 401


def test_bad_token_rejected(anon_client):
    resp = anon_client.get(
        "/incidents", headers={"Authorization": "Bearer not-a-real-token"}
    )
    assert resp.status_code == 401


def test_viewer_cannot_create_incident(role_client):
    client = role_client("viewer")
    resp = client.post(
        "/incidents",
        json={"title": "Should be forbidden", "severity": "high"},
    )
    assert resp.status_code == 403


def test_operator_can_create_incident(role_client):
    client = role_client("operator")
    resp = client.post(
        "/incidents",
        json={"title": "Operator-created incident", "severity": "high"},
    )
    assert resp.status_code == 201


def test_viewer_can_list_incidents(role_client):
    client = role_client("viewer")
    resp = client.get("/incidents")
    assert resp.status_code == 200


def test_api_key_auth_and_role_gate(anon_client, db_session):
    from app.core.security import create_access_token, hash_password
    from app.repositories.user_repository import create_user

    admin = create_user(
        db_session,
        email="api-admin@incidentpilot.example",
        hashed_password=hash_password("irrelevant"),
        role="admin",
    )
    db_session.commit()
    admin_token = create_access_token(user_id=admin.id, email=admin.email, role=admin.role)

    issue_resp = anon_client.post(
        "/auth/api-keys",
        json={"email": "service-account@incidentpilot.example", "role": "operator"},
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert issue_resp.status_code == 200
    api_key = issue_resp.json()["api_key"]

    resp = anon_client.post(
        "/incidents",
        json={"title": "Created via API key", "severity": "medium"},
        headers={"X-API-Key": api_key},
    )
    assert resp.status_code == 201

    unauthorized = anon_client.post(
        "/auth/api-keys",
        json={"email": "another@incidentpilot.example", "role": "admin"},
        headers={"X-API-Key": api_key},
    )
    assert unauthorized.status_code == 403


def test_invalid_api_key_rejected(anon_client):
    resp = anon_client.get("/incidents", headers={"X-API-Key": "not-a-real-key"})
    assert resp.status_code == 401
