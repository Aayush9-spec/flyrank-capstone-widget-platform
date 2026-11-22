
import pytest
from app.core.rate_limit import limiter

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.database import Base, get_db
from app.main import app

@pytest.fixture(autouse=True)
def reset_rate_limiter():
    limiter.reset()
    yield
    limiter.reset()

@pytest.fixture
def client():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )

    Base.metadata.create_all(engine)

    TestSession = sessionmaker(
        bind=engine,
        autoflush=False,
        autocommit=False,
        expire_on_commit=False,
    )

    def override_get_db():
        db = TestSession()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override_get_db

    with TestClient(app) as test_client:
        yield test_client

    app.dependency_overrides.clear()
    Base.metadata.drop_all(engine)
    engine.dispose()


@pytest.fixture
def user_headers(client):
    response = client.post(
        "/api/auth/register",
        json={
            "tenant_name": "Test Company",
            "email": "owner@example.com",
            "password": "SecureTestPass123!",
        },
    )

    assert response.status_code == 201, response.text

    login = client.post(
        "/api/auth/login",
        json={
            "email": "owner@example.com",
            "password": "SecureTestPass123!",
        },
    )

    assert login.status_code == 200, login.text

    token = login.json()["access_token"]

    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def widget(client, user_headers):
    response = client.post(
        "/api/widgets",
        headers=user_headers,
        json={
            "name": "Integration Test Widget",
            "configuration": {
                "title": "Contact Us",
                "submit_text": "Send",
                "fields": [
                    {
                        "name": "name",
                        "type": "text",
                        "required": True,
                    },
                    {
                        "name": "email",
                        "type": "email",
                        "required": True,
                    },
                    {
                        "name": "message",
                        "type": "textarea",
                        "required": False,
                    },
                ],
            },
            "allowed_origins": ["http://localhost:5500"],
        },
    )

    assert response.status_code == 201, response.text

    return response.json()
