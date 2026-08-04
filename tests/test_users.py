def test_list_users_role_access(role_client):
    viewer_client = role_client("viewer")
    assert viewer_client.get("/users").status_code == 403

    operator_client = role_client("operator")
    assert operator_client.get("/users").status_code == 403

    admin_client = role_client("admin")
    resp = admin_client.get("/users")
    assert resp.status_code == 200
    assert isinstance(resp.json(), list)


def test_create_user_admin_only(role_client):
    admin_client = role_client("admin")
    resp = admin_client.post(
        "/users",
        json={
            "email": "new-user@incidentpilot.example",
            "password": "secret-password-123",
            "role": "operator",
        },
    )
    assert resp.status_code == 201
    data = resp.json()
    assert data["email"] == "new-user@incidentpilot.example"
    assert data["role"] == "operator"
    assert data["is_active"] is True
    assert data["has_api_key"] is False


def test_create_duplicate_user_rejected(role_client):
    admin_client = role_client("admin")
    payload = {
        "email": "duplicate@incidentpilot.example",
        "password": "secret-password-123",
        "role": "viewer",
    }
    assert admin_client.post("/users", json=payload).status_code == 201
    dup_resp = admin_client.post("/users", json=payload)
    assert dup_resp.status_code == 400
    assert "already exists" in dup_resp.json()["detail"]


def test_update_user_role(role_client):
    admin_client = role_client("admin")
    create_resp = admin_client.post(
        "/users",
        json={
            "email": "role-change@incidentpilot.example",
            "password": "secret-password-123",
            "role": "viewer",
        },
    )
    user_id = create_resp.json()["id"]

    patch_resp = admin_client.patch(
        f"/users/{user_id}/role",
        json={"role": "operator"},
    )
    assert patch_resp.status_code == 200
    assert patch_resp.json()["role"] == "operator"


def test_update_user_status(role_client):
    admin_client = role_client("admin")
    create_resp = admin_client.post(
        "/users",
        json={
            "email": "deactivate-me@incidentpilot.example",
            "password": "secret-password-123",
            "role": "viewer",
        },
    )
    user_id = create_resp.json()["id"]

    patch_resp = admin_client.patch(
        f"/users/{user_id}/status",
        json={"is_active": False},
    )
    assert patch_resp.status_code == 200
    assert patch_resp.json()["is_active"] is False


def test_delete_user(role_client):
    admin_client = role_client("admin")
    create_resp = admin_client.post(
        "/users",
        json={
            "email": "delete-me@incidentpilot.example",
            "password": "secret-password-123",
            "role": "viewer",
        },
    )
    user_id = create_resp.json()["id"]

    del_resp = admin_client.delete(f"/users/{user_id}")
    assert del_resp.status_code == 204
