from fastapi import APIRouter, Depends, Header, HTTPException, Response
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.models.models import Widget


router = APIRouter(prefix="/api/public", tags=["Public Widget"])


@router.get("/widgets/{public_id}/config")
def get_public_widget_config(
    public_id: str,
    response: Response,
    origin: str | None = Header(default=None),
    if_none_match: str | None = Header(default=None),
    db: Session = Depends(get_db),
):
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

    response.headers["Access-Control-Allow-Origin"] = origin
    response.headers["Vary"] = "Origin"
    response.headers["Cache-Control"] = "public, max-age=60"
    etag = f'"widget-{widget.public_id}-v{widget.version}"'
    response.headers["ETag"] = etag

    if if_none_match and etag in [tag.strip() for tag in if_none_match.split(",")]:
        response.status_code = 304
        return Response(status_code=304, headers=dict(response.headers))

    return {
        "public_id": widget.public_id,
        "name": widget.name,
        "configuration": widget.configuration,
        "version": widget.version,
    }
