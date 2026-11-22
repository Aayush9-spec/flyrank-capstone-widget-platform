from fastapi import APIRouter, Depends, Query
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.api.dependencies import get_current_user
from app.core.database import get_db
from app.models.models import Submission, Widget, User


router = APIRouter(prefix="/api/dashboard", tags=["Owner Dashboard"])


@router.get("/submissions")
def list_submissions(
    limit: int = Query(default=50, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    submissions = (
        db.query(Submission)
        .filter(Submission.tenant_id == current_user.tenant_id)
        .order_by(Submission.created_at.desc())
        .offset(offset)
        .limit(limit)
        .all()
    )

    return {
        "total": db.query(func.count(Submission.id))
        .filter(Submission.tenant_id == current_user.tenant_id)
        .scalar(),
        "items": [
            {
                "id": item.id,
                "widget_id": item.widget_id,
                "data": item.data,
                "country": item.country,
                "city": item.city,
                "created_at": item.created_at.isoformat(),
            }
            for item in submissions
        ],
    }


@router.get("/stats")
def dashboard_stats(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    tenant_id = current_user.tenant_id

    widget_count = (
        db.query(func.count(Widget.id))
        .filter(Widget.tenant_id == tenant_id)
        .scalar()
    )

    submission_count = (
        db.query(func.count(Submission.id))
        .filter(Submission.tenant_id == tenant_id)
        .scalar()
    )

    return {
        "widgets": widget_count,
        "submissions": submission_count,
    }
