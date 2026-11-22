def test_health_endpoints(client):
    assert client.get("/").status_code == 200
    assert client.get("/health").status_code == 200


def test_duplicate_registration_and_invalid_login(client, user_headers):
    duplicate = client.post(
        "/api/auth/register",
        json={
            "tenant_name": "Another Company",
            "email": "owner@example.com",
            "password": "SecureTestPass123!",
        },
    )
    assert duplicate.status_code == 409

    invalid_login = client.post(
        "/api/auth/login",
        json={
            "email": "owner@example.com",
            "password": "WrongPassword123!",
        },
    )
    assert invalid_login.status_code == 401


def test_widget_crud(client, widget, user_headers):
    widget_id = widget["id"]

    response = client.get(
        f"/api/widgets/{widget_id}",
        headers=user_headers,
    )
    assert response.status_code == 200

    updated = client.patch(
        f"/api/widgets/{widget_id}",
        headers=user_headers,
        json={"name": "Updated Integration Widget"},
    )
    assert updated.status_code == 200
    assert updated.json()["name"] == "Updated Integration Widget"

    deleted = client.delete(
        f"/api/widgets/{widget_id}",
        headers=user_headers,
    )
    assert deleted.status_code in (200, 204)

    missing = client.get(
        f"/api/widgets/{widget_id}",
        headers=user_headers,
    )
    assert missing.status_code == 404


def test_widget_tenant_isolation(client, widget, user_headers):
    registration = client.post(
        "/api/auth/register",
        json={
            "tenant_name": "Second Company",
            "email": "second@example.com",
            "password": "AnotherSecurePass123!",
        },
    )
    assert registration.status_code == 201

    login = client.post(
        "/api/auth/login",
        json={
            "email": "second@example.com",
            "password": "AnotherSecurePass123!",
        },
    )
    assert login.status_code == 200

    other_headers = {
        "Authorization": f"Bearer {login.json()['access_token']}"
    }

    response = client.get(
        f"/api/widgets/{widget['id']}",
        headers=other_headers,
    )
    assert response.status_code == 404

    listing = client.get("/api/widgets", headers=other_headers)
    assert listing.status_code == 200
    assert listing.json() == []


def test_public_config_origin_and_cache(client, widget):
    public_id = widget["public_id"]

    response = client.get(
        f"/api/public/widgets/{public_id}/config",
        headers={"Origin": "http://localhost:5500"},
    )
    assert response.status_code == 200
    assert "public" in response.headers["cache-control"]
    assert "etag" in response.headers

    etag = response.headers["etag"]

    cached = client.get(
        f"/api/public/widgets/{public_id}/config",
        headers={
            "Origin": "http://localhost:5500",
            "If-None-Match": etag,
        },
    )
    assert cached.status_code == 304

    blocked = client.get(
        f"/api/public/widgets/{public_id}/config",
        headers={"Origin": "https://untrusted.example"},
    )
    assert blocked.status_code == 403


def test_submission_and_idempotency(client, widget, user_headers, monkeypatch):
    from app.api import submissions

    monkeypatch.setattr(
    submissions,
    "get_location",
    lambda visitor_ip: None,
    )

    url = (
        f"/api/public/widgets/{widget['public_id']}/submissions"
    )
    headers = {
        "Origin": "http://localhost:5500",
        "Idempotency-Key": "integration-test-key-001",
    }
    payload = {
        "data": {
            "name": "Integration Lead",
            "email": "lead@example.com",
            "message": "Testing lead capture",
        }
    }

    first = client.post(url, json=payload, headers=headers)
    assert first.status_code == 201, first.text

    second = client.post(url, json=payload, headers=headers)
    assert second.status_code == 200, second.text
    assert second.json()["id"] == first.json()["id"]

    dashboard = client.get(
        "/api/dashboard/submissions",
        headers=user_headers,
    )
    assert dashboard.status_code == 200
    assert "lead@example.com" in dashboard.text

def test_submission_validation_and_honeypot(client, widget):
    url = f"/api/public/widgets/{widget['public_id']}/submissions"
    headers = {"Origin": "http://localhost:5500"}

    # Missing required name and email
    missing = client.post(
        url,
        json={"data": {"message": "Incomplete submission"}},
        headers=headers,
    )
    assert missing.status_code == 422

    # Invalid email
    invalid_email = client.post(
        url,
        json={"data": {"name": "Test", "email": "not-an-email"}},
        headers=headers,
    )
    assert invalid_email.status_code == 422

    # Honeypot spam attempt
    spam = client.post(
        url,
        json={
            "data": {
                "name": "Bot",
                "email": "bot@example.com",
                "website": "https://spam.example",
            }
        },
        headers=headers,
    )
    assert spam.status_code == 422


def test_dashboard_stats(client, widget, user_headers):
    response = client.get(
        "/api/dashboard/stats",
        headers=user_headers,
    )
    assert response.status_code == 200
    assert isinstance(response.json(), dict)


def test_dashboard_requires_authentication(client):
    response = client.get("/api/dashboard/submissions")
    assert response.status_code in (401, 403)

def test_submission_preflight_and_origin_rejection(client, widget):
    public_id = widget["public_id"]
    url = f"/api/public/widgets/{public_id}/submissions"

    response = client.options(
        url,
        headers={"Origin": "http://localhost:5500"},
    )

    assert response.status_code == 204
    assert response.headers["access-control-allow-origin"] == "http://localhost:5500"
    assert "POST" in response.headers["access-control-allow-methods"]

    rejected = client.options(
        url,
        headers={"Origin": "http://malicious.example"},
    )

    assert rejected.status_code == 403


def test_submission_rejects_invalid_idempotency_keys(client, widget):
    url = f"/api/public/widgets/{widget['public_id']}/submissions"
    headers = {"Origin": "http://localhost:5500"}
    payload = {"data": {"name": "Test", "email": "test@example.com"}}

    for key in ("", " "):
        response = client.post(
            url,
            headers={**headers, "Idempotency-Key": key},
            json=payload,
        )
        assert response.status_code == 422

    response = client.post(
        url,
        headers={**headers, "Idempotency-Key": "x" * 129},
        json=payload,
    )
    assert response.status_code == 422


def test_submission_without_idempotency_key(client, widget, monkeypatch):
    from app.api import submissions

    monkeypatch.setattr(submissions, "get_location", lambda ip: None)

    url = f"/api/public/widgets/{widget['public_id']}/submissions"

    response = client.post(
        url,
        headers={"Origin": "http://localhost:5500"},
        json={"data": {"name": "No Key", "email": "nokey@example.com"}},
    )

    assert response.status_code == 201
    assert response.json()["status"] == "received"


def test_geo_exception_does_not_block_submission(client, widget, monkeypatch):
    from app.api import submissions

    def fail_lookup(ip):
        raise RuntimeError("Geo provider unavailable")

    monkeypatch.setattr(submissions, "get_location", fail_lookup)

    response = client.post(
        f"/api/public/widgets/{widget['public_id']}/submissions",
        headers={"Origin": "http://localhost:5500"},
        json={"data": {"name": "Geo Failure", "email": "geo@example.com"}},
    )

    assert response.status_code == 201
    assert response.json()["status"] == "received"


def test_submission_rejects_unknown_and_inactive_widgets(client):
    from app.models.models import Widget

    missing = client.post(
        "/api/public/widgets/unknown-widget/submissions",
        headers={"Origin": "http://localhost:5500"},
        json={"data": {"name": "Test", "email": "test@example.com"}},
    )
    assert missing.status_code == 404

def test_inactive_widget_rejects_submission(client, widget):
    from app.main import app
    from app.models.models import Widget
    from app.core.database import get_db

    db_generator = app.dependency_overrides[get_db]()
    db = next(db_generator)

    try:
        record = db.query(Widget).filter(
            Widget.id == widget["id"]
        ).first()

        record.is_active = False
        db.commit()
    finally:
        db_generator.close()

    response = client.post(
        f"/api/public/widgets/{widget['public_id']}/submissions",
        headers={"Origin": "http://localhost:5500"},
        json={
            "data": {
                "name": "Inactive Test",
                "email": "inactive@example.com",
            }
        },
    )

    assert response.status_code == 404