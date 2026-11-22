import uuid

from fastapi import APIRouter, Depends, Header, HTTPException, Request, Response
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.config import settings
from app.core.rate_limit import limiter
from app.models.models import NotificationJob, Submission, Widget
from app.schemas.submission import SubmissionCreate
from app.services.submission import validate_submission
from app.services.geo import get_location


router = APIRouter(prefix="/api/public", tags=["Lead Submissions"])


def get_allowed_widget(db: Session, public_id: str, origin: str | None):
    widget = (
        db.query(Widget)
        .filter(
            Widget.public_id == public_id,
            Widget.is_active.is_(True),
        )
        .first()
    )

    if widget is None:
        raise HTTPException(status_code=404, detail="Widget not found")

    if not origin or origin not in widget.allowed_origins:
        raise HTTPException(status_code=403, detail="Origin not allowed")

    return widget


def set_cors_headers(response: Response, origin: str):
    response.headers["Access-Control-Allow-Origin"] = origin
    response.headers["Access-Control-Allow-Methods"] = "POST, OPTIONS"
    response.headers["Access-Control-Allow-Headers"] = (
        "Content-Type, Idempotency-Key"
    )
    response.headers["Vary"] = "Origin"


@router.options("/widgets/{public_id}/submissions")
def submission_preflight(
    public_id: str,
    response: Response,
    origin: str | None = Header(default=None),
    db: Session = Depends(get_db),
):
    get_allowed_widget(db, public_id, origin)
    set_cors_headers(response, origin)
    return Response(status_code=204, headers=dict(response.headers))


@router.post("/widgets/{public_id}/submissions")
@limiter.limit(f"{settings.RATE_LIMIT_PER_MINUTE}/minute")
def create_submission(
    public_id: str,
    payload: SubmissionCreate,
    request: Request,
    response: Response,
    origin: str | None = Header(default=None),
    idempotency_key: str | None = Header(
        default=None, alias="Idempotency-Key"
    ),
    db: Session = Depends(get_db),
):
    widget = get_allowed_widget(db, public_id, origin)
    cleaned_data = validate_submission(widget, payload.data)

    if idempotency_key is not None:
        idempotency_key = idempotency_key.strip()

        if not idempotency_key or len(idempotency_key) > 128:
            raise HTTPException(
                status_code=422,
                detail="Idempotency-Key must contain 1–128 characters",
            )

        existing = (
            db.query(Submission)
            .filter(
                Submission.widget_id == widget.id,
                Submission.idempotency_key == idempotency_key,
            )
            .first()
        )

        if existing:
            set_cors_headers(response, origin)
            response.status_code = 200
            return {
                "id": existing.id,
                "status": "already_received",
            }

    visitor_ip = request.client.host if request.client else None

    try:
        location = get_location(visitor_ip)
    except Exception:
        location = None

    submission = Submission(
        tenant_id=widget.tenant_id,
        widget_id=widget.id,
        idempotency_key=idempotency_key,
        data=cleaned_data,
        visitor_ip=visitor_ip,
        country=location.get("country") if location else None,
        city=location.get("city") if location else None,
    )

    try:
        db.add(submission)
        db.flush()

        job = NotificationJob(
            tenant_id=widget.tenant_id,
            widget_id=widget.id,
            submission_id=submission.id,
        )

        db.add(job)
        db.commit()
        db.refresh(submission)

    except IntegrityError:
        db.rollback()

        if idempotency_key:
            existing = (
                db.query(Submission)
                .filter(
                    Submission.widget_id == widget.id,
                    Submission.idempotency_key == idempotency_key,
                )
                .first()
            )

            if existing:
                set_cors_headers(response, origin)
                response.status_code = 200
                return {
                    "id": existing.id,
                    "status": "already_received",
                }

        raise HTTPException(status_code=409, detail="Submission conflict")

    set_cors_headers(response, origin)
    response.status_code = 201

    return {
        "id": submission.id,
        "status": "received",
        "created_at": submission.created_at.isoformat(),
    }
