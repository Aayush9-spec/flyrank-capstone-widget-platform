import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.api.dependencies import get_current_user
from app.core.database import get_db
from app.models.models import User, Widget
from app.schemas.widget import WidgetCreate, WidgetUpdate, WidgetResponse


router = APIRouter(prefix="/api/widgets", tags=["Widgets"])


@router.post(
    "",
    response_model=WidgetResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_widget(
    payload: WidgetCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    widget = Widget(
        tenant_id=current_user.tenant_id,
        name=payload.name,
        public_id=uuid.uuid4().hex,
        configuration=payload.configuration,
        allowed_origins=payload.allowed_origins,
    )

    db.add(widget)
    db.commit()
    db.refresh(widget)

    return widget


@router.get("", response_model=list[WidgetResponse])
def list_widgets(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return (
        db.query(Widget)
        .filter(Widget.tenant_id == current_user.tenant_id)
        .order_by(Widget.created_at.desc())
        .all()
    )


@router.get("/{widget_id}", response_model=WidgetResponse)
def get_widget(
    widget_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    widget = (
        db.query(Widget)
        .filter(
            Widget.id == widget_id,
            Widget.tenant_id == current_user.tenant_id,
        )
        .first()
    )

    if widget is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Widget not found",
        )

    return widget


@router.patch("/{widget_id}", response_model=WidgetResponse)
def update_widget(
    widget_id: str,
    payload: WidgetUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    widget = (
        db.query(Widget)
        .filter(
            Widget.id == widget_id,
            Widget.tenant_id == current_user.tenant_id,
        )
        .first()
    )

    if widget is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Widget not found",
        )

    changes = payload.model_dump(exclude_unset=True)

    if "name" in changes and changes["name"] is None:
        raise HTTPException(status_code=422, detail="Widget name cannot be null")

    if "configuration" in changes and changes["configuration"] is None:
        raise HTTPException(status_code=422, detail="Configuration cannot be null")

    if "allowed_origins" in changes and changes["allowed_origins"] is None:
        raise HTTPException(status_code=422, detail="Allowed origins cannot be null")

    for field, value in changes.items():
        if getattr(widget, field) != value:
            setattr(widget, field, value)
            if field in {"name", "configuration", "allowed_origins"}:
                widget.version += 1

    db.commit()
    db.refresh(widget)

    return widget


@router.delete("/{widget_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_widget(
    widget_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    widget = (
        db.query(Widget)
        .filter(
            Widget.id == widget_id,
            Widget.tenant_id == current_user.tenant_id,
        )
        .first()
    )

    if widget is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Widget not found",
        )

    db.delete(widget)
    db.commit()
