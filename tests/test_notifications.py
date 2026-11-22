
from datetime import datetime, timedelta, timezone

import pytest
from types import SimpleNamespace
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.database import Base
from app.models.models import (
    NotificationJob,
    Submission,
    Tenant,
    Widget,
)
from app.workers import notifications as worker


@pytest.fixture
def db_setup(monkeypatch):
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    TestSession = sessionmaker(bind=engine, expire_on_commit=False)

    tenant_id = "test-tenant"
    widget_id = "test-widget"
    submission_id = "test-submission"

    with TestSession() as db:
        db.add(Tenant(id=tenant_id, name="Test Tenant"))
        db.add(
            Widget(
                id=widget_id,
                tenant_id=tenant_id,
                name="Test Widget",
                configuration={},
                allowed_origins=[],
            )
        )
        db.add(
            Submission(
                id=submission_id,
                tenant_id=tenant_id,
                widget_id=widget_id,
                data={"name": "Test Lead", "email": "test@example.com"},
            )
        )
        db.add(
            NotificationJob(
                id="test-job",
                tenant_id=tenant_id,
                widget_id=widget_id,
                submission_id=submission_id,
                status="pending",
                attempts=0,
                max_attempts=3,
            )
        )
        db.commit()

    monkeypatch.setattr(worker, "SessionLocal", TestSession)
    monkeypatch.setattr(worker.settings, "NOTIFICATION_MAX_ATTEMPTS", 3)
    monkeypatch.setattr(worker.settings, "NOTIFICATION_WEBHOOK_URL", "")
    monkeypatch.setattr(worker.settings, "NOTIFICATION_EMAIL_TO", "")

    yield TestSession

    Base.metadata.drop_all(engine)
    engine.dispose()


def get_job(TestSession):
    with TestSession() as db:
        return db.get(NotificationJob, "test-job")


def test_successful_delivery(db_setup, monkeypatch):
    monkeypatch.setattr(
        worker.settings,
        "NOTIFICATION_WEBHOOK_URL",
        "https://example.com/webhook",
    )
    monkeypatch.setattr(
        worker,
        "deliver_notification",
        lambda submission: None,
    )

    assert worker.process_one_job() is True

    job = get_job(db_setup)
    assert job.status == "sent"
    assert job.attempts == 1
    assert job.last_error is None
    assert job.next_attempt_at is None


def test_retry_after_delivery_failure(db_setup, monkeypatch):
    monkeypatch.setattr(
        worker,
        "deliver_notification",
        lambda submission: (_ for _ in ()).throw(
            RuntimeError("Temporary delivery failure")
        ),
    )
    monkeypatch.setattr(
        worker.settings,
        "NOTIFICATION_WEBHOOK_URL",
        "https://example.invalid/webhook",
    )

    assert worker.process_one_job() is True

    job = get_job(db_setup)
    assert job.status == "retry"
    assert job.attempts == 1
    assert "Temporary delivery failure" in job.last_error
    assert job.next_attempt_at is not None


def test_permanent_failure_alert(db_setup, monkeypatch):
    with db_setup() as db:
        job = db.get(NotificationJob, "test-job")
        job.attempts = 2
        db.commit()

    monkeypatch.setattr(
        worker,
        "deliver_notification",
        lambda submission: (_ for _ in ()).throw(
            RuntimeError("Permanent delivery failure")
        ),
    )
    monkeypatch.setattr(
        worker.settings,
        "NOTIFICATION_WEBHOOK_URL",
        "https://example.invalid/webhook",
    )

    alerts = []
    monkeypatch.setattr(
        worker,
        "alert_terminal_failure",
        lambda job_id, error: alerts.append((job_id, error)),
    )

    assert worker.process_one_job() is True

    job = get_job(db_setup)
    assert job.status == "failed"
    assert job.attempts == 3
    assert len(alerts) == 1
    assert alerts[0][0] == "test-job"


def test_recover_expired_processing_job(db_setup, monkeypatch):
    with db_setup() as db:
        job = db.get(NotificationJob, "test-job")
        job.status = "processing"
        job.attempts = 1
        job.next_attempt_at = datetime.now(timezone.utc) - timedelta(minutes=3)
        db.commit()

    monkeypatch.setattr(
        worker,
        "deliver_notification",
        lambda submission: None,
    )

    assert worker.process_one_job() is True

    job = get_job(db_setup)
    assert job.status == "skipped"
    assert job.attempts == 2


def make_submission():
    return SimpleNamespace(
        id="test-submission",
        widget_id="test-widget",
        data={"name": "Test Lead", "email": "test@example.com"},
        created_at=datetime.now(timezone.utc),
    )


def test_webhook_delivery_sends_payload_and_idempotency_key(monkeypatch):
    calls = {}

    class Response:
        def raise_for_status(self):
            calls["raised"] = True

    def fake_post(url, **kwargs):
        calls["url"] = url
        calls.update(kwargs)
        return Response()

    monkeypatch.setattr(worker.httpx, "post", fake_post)
    monkeypatch.setattr(
        worker.settings,
        "NOTIFICATION_WEBHOOK_URL",
        "https://example.com/webhook",
    )
    monkeypatch.setattr(worker.settings, "NOTIFICATION_EMAIL_TO", "")

    worker.deliver_notification(make_submission())

    assert calls["json"]["event"] == "lead.created"
    assert calls["json"]["submission_id"] == "test-submission"
    assert calls["headers"]["Idempotency-Key"] == "test-submission"
    assert calls["raised"] is True


def test_email_notification_calls_send_email(monkeypatch):
    sent = []

    monkeypatch.setattr(worker.settings, "NOTIFICATION_WEBHOOK_URL", "")
    monkeypatch.setattr(
        worker.settings,
        "NOTIFICATION_EMAIL_TO",
        "owner@example.com",
    )
    monkeypatch.setattr(
        worker,
        "send_email",
        lambda *args: sent.append(args),
    )

    worker.deliver_notification(make_submission())

    assert len(sent) == 1
    assert sent[0][0] == "owner@example.com"
    assert "New widget lead" in sent[0][1]
    assert "Test Lead" in sent[0][2]


def test_no_destination_skips_delivery(monkeypatch, caplog):
    monkeypatch.setattr(worker.settings, "NOTIFICATION_WEBHOOK_URL", "")
    monkeypatch.setattr(worker.settings, "NOTIFICATION_EMAIL_TO", "")

    with caplog.at_level("INFO", logger=worker.__name__):
        worker.deliver_notification(make_submission())

    assert "No notification destination configured" in caplog.text


def test_send_email_uses_smtp(monkeypatch):
    calls = {}

    class FakeSMTP:
        def __init__(self, host, port, timeout):
            calls["connection"] = (host, port, timeout)

        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

        def starttls(self):
            calls["tls"] = True

        def login(self, username, password):
            calls["login"] = (username, password)

        def send_message(self, message):
            calls["message"] = message

    monkeypatch.setattr(worker.smtplib, "SMTP", FakeSMTP)
    monkeypatch.setattr(worker.settings, "SMTP_HOST", "smtp.example.com")
    monkeypatch.setattr(worker.settings, "SMTP_PORT", 587)
    monkeypatch.setattr(worker.settings, "SMTP_FROM_EMAIL", "noreply@example.com")
    monkeypatch.setattr(worker.settings, "SMTP_USE_TLS", True)
    monkeypatch.setattr(worker.settings, "SMTP_USERNAME", "smtp-user")
    monkeypatch.setattr(worker.settings, "SMTP_PASSWORD", "test-password")

    worker.send_email("owner@example.com", "Test subject", "Test body")

    assert calls["connection"] == ("smtp.example.com", 587, 10)
    assert calls["tls"] is True
    assert calls["login"] == ("smtp-user", "test-password")
    assert calls["message"]["To"] == "owner@example.com"
    assert calls["message"]["Subject"] == "Test subject"


def test_send_email_rejects_missing_configuration(monkeypatch):
    monkeypatch.setattr(worker.settings, "SMTP_HOST", "")
    monkeypatch.setattr(worker.settings, "SMTP_FROM_EMAIL", "")

    with pytest.raises(RuntimeError, match="SMTP is not configured"):
        worker.send_email("owner@example.com", "Subject", "Body")


def test_terminal_failure_sends_alert_email(monkeypatch):
    sent = []

    monkeypatch.setattr(
        worker.settings,
        "NOTIFICATION_FAILURE_ALERT_EMAIL",
        "alerts@example.com",
    )
    monkeypatch.setattr(
        worker,
        "send_email",
        lambda *args: sent.append(args),
    )

    worker.alert_terminal_failure("job-123", "Delivery failed")

    assert len(sent) == 1
    assert sent[0][0] == "alerts@example.com"
    assert "permanently failed" in sent[0][1]
    assert "job-123" in sent[0][2]
