def test_register_rate_limit(client):
    for i in range(3):
        response = client.post(
            "/api/auth/register",
            json={
                "tenant_name": f"Company {i}",
                "email": f"owner{i}@example.com",
                "password": "SecureTestPass123!",
            },
        )
        assert response.status_code == 201, response.text

    response = client.post(
        "/api/auth/register",
        json={
            "tenant_name": "Company 4",
            "email": "owner4@example.com",
            "password": "SecureTestPass123!",
        },
    )

    assert response.status_code == 429


def test_login_rate_limit(client):
    registration = client.post(
        "/api/auth/register",
        json={
            "tenant_name": "Login Test Company",
            "email": "login-test@example.com",
            "password": "SecureTestPass123!",
        },
    )

    assert registration.status_code == 201, registration.text

    for _ in range(5):
        response = client.post(
            "/api/auth/login",
            json={
                "email": "login-test@example.com",
                "password": "WrongPassword123!",
            },
        )
        assert response.status_code == 401, response.text

    response = client.post(
        "/api/auth/login",
        json={
            "email": "login-test@example.com",
            "password": "WrongPassword123!",
        },
    )

    assert response.status_code == 429
