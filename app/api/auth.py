from fastapi import APIRouter, Depends, HTTPException, Request, status
from app.core.config import settings
from app.core.rate_limit import limiter
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.security import (
    create_access_token,
    hash_password,
    verify_password,
)
from app.models.models import Tenant, User
from app.schemas.auth import (
    LoginRequest,
    RegisterRequest,
    TokenResponse,
    UserResponse,
)


router = APIRouter(prefix="/api/auth", tags=["Authentication"])


@router.post(
    "/register",
    response_model=UserResponse,
    status_code=status.HTTP_201_CREATED,
)

@limiter.limit(
    f"{settings.AUTH_REGISTER_RATE_LIMIT_PER_MINUTE}/minute"
)

def register(
    payload: RegisterRequest,
    request: Request,
    db: Session = Depends(get_db),
):

    email = payload.email.lower().strip()

    existing_user = db.query(User).filter(User.email == email).first()

    if existing_user:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="An account with this email already exists",
        )

    tenant = Tenant(name=payload.tenant_name.strip())

    user = User(
        tenant=tenant,
        email=email,
        hashed_password=hash_password(payload.password),
    )

    try:
        db.add(user)
        db.commit()
        db.refresh(user)
        return user

    except IntegrityError:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="An account with this email already exists",
        )


@router.post("/login", response_model=TokenResponse)
@limiter.limit(
    f"{settings.AUTH_LOGIN_RATE_LIMIT_PER_MINUTE}/minute"
)
def login(
    payload: LoginRequest,
    request: Request,
    db: Session = Depends(get_db),
):
    email = payload.email.lower().strip()

    user = db.query(User).filter(User.email == email).first()

    if (
        user is None
        or not user.is_active
        or not verify_password(payload.password, user.hashed_password)
    ):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password",
            headers={"WWW-Authenticate": "Bearer"},
        )

    token = create_access_token(user.id)

    return TokenResponse(access_token=token)
