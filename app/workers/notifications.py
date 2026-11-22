import json
import logging
import smtplib
import time
from datetime import datetime, timedelta, timezone
from email.message import EmailMessage

import httpx
from sqlalchemy import or_, select

from app.core.config import settings
from app.core.database import SessionLocal
from app.models.models import NotificationJob, Submission

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
)
logger = logging.getLogger(__name__)


def send_email(recipient: str, subject: str, body: str) -> None:
    if not all([settings.SMTP_HOST, settings.SMTP_FROM_EMAIL]):
        raise RuntimeError("SMTP is not configured")

    message = EmailMessage()
    message["From"] = settings.SMTP_FROM_EMAIL
    message["To"] = recipient
    message["Subject"] = subject
    message.set_content(body)

    with smtplib.SMTP(
        settings.SMTP_HOST,
        settings.SMTP_PORT,
        timeout=10,
    ) as server:
        if settings.SMTP_USE_TLS:
            server.starttls()
        if settings.SMTP_USERNAME:
            server.login(settings.SMTP_USERNAME, settings.SMTP_PASSWORD)
        server.send_message(message)


def deliver_notification(submission: Submission) -> None:
    destinations = []

    if settings.NOTIFICATION_WEBHOOK_URL:
        payload = {
            "event": "lead.created",
            "submission_id": submission.id,
            "widget_id": submission.widget_id,
            "data": submission.data,
            "created_at": submission.created_at.isoformat(),
        }
        response = httpx.post(
            settings.NOTIFICATION_WEBHOOK_URL,
            json=payload,
            headers={"Idempotency-Key": submission.id},
            timeout=10,
        )
        response.raise_for_status()
        destinations.append("webhook")

    if settings.NOTIFICATION_EMAIL_TO:
        body = (
            f"New lead received\n\n"
            f"Widget: {submission.widget_id}\n"
            f"Submission: {submission.id}\n\n"
            f"{json.dumps(submission.data, indent=2, ensure_ascii=False)}"
        )
        send_email(
            settings.NOTIFICATION_EMAIL_TO,
            "New widget lead",
            body,
        )
        destinations.append("email")

    if not destinations:
        logger.info("No notification destination configured; skipping delivery")
    else:
        logger.info("Notification delivered through: %s", ", ".join(destinations))


def alert_terminal_failure(job_id: str, error: str) -> None:
    logger.critical(
        "Notification job %s permanently failed: %s",
        job_id,
        error,
    )

    if settings.NOTIFICATION_FAILURE_ALERT_EMAIL:
        try:
            send_email(
                settings.NOTIFICATION_FAILURE_ALERT_EMAIL,
                "Widget notification job permanently failed",
                f"Job ID: {job_id}\nError: {error}",
            )
        except Exception:
            logger.exception("Could not send notification failure alert")


def process_one_job() -> bool:
    now = datetime.now(timezone.utc)

    with SessionLocal() as db:
        job = db.execute(
            select(NotificationJob)
            .where(
                NotificationJob.status.in_(["pending", "retry", "processing"]),
                or_(
                    NotificationJob.next_attempt_at.is_(None),
                    NotificationJob.next_attempt_at <= now,
                ),
            )
            .order_by(NotificationJob.created_at)
            .with_for_update(skip_locked=True)
        ).scalars().first()

        if job is None:
            return False

        job.status = "processing"
        job.attempts += 1
        job.next_attempt_at = now + timedelta(minutes=2)
        job.max_attempts = settings.NOTIFICATION_MAX_ATTEMPTS
        job_id = job.id
        submission_id = job.submission_id
        db.commit()

    try:
        with SessionLocal() as db:
            submission = db.get(Submission, submission_id)
            if submission is None:
                raise RuntimeError("Associated submission no longer exists")

            deliver_notification(submission)

        with SessionLocal() as db:
            job = db.get(NotificationJob, job_id)
            if job:
                job.status = "skipped" if not (
                    settings.NOTIFICATION_WEBHOOK_URL
                    or settings.NOTIFICATION_EMAIL_TO
                ) else "sent"
                job.last_error = None
                job.next_attempt_at = None
                db.commit()

        return True

    except Exception as exc:
        error = str(exc)[:1000]
        terminal = False

        with SessionLocal() as db:
            job = db.get(NotificationJob, job_id)
            if job:
                job.last_error = error

                if job.attempts >= job.max_attempts:
                    job.status = "failed"
                    job.next_attempt_at = None
                    terminal = True
                else:
                    job.status = "retry"
                    delay = min(2 ** job.attempts, 300)
                    job.next_attempt_at = (
                        datetime.now(timezone.utc) + timedelta(seconds=delay)
                    )

                db.commit()

        logger.exception("Notification job %s failed", job_id)

        if terminal:
            alert_terminal_failure(job_id, error)

        return True


def main() -> None:
    logger.info("Notification worker started")

    while True:
        try:
            processed = process_one_job()
            if not processed:
                time.sleep(max(1, settings.NOTIFICATION_POLL_SECONDS))
        except KeyboardInterrupt:
            logger.info("Notification worker stopped")
            break
        except Exception:
            logger.exception("Worker loop error")
            time.sleep(max(1, settings.NOTIFICATION_POLL_SECONDS))


if __name__ == "__main__":
    main()