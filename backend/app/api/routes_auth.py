from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.auth import (
    AuthPrincipal,
    ROLE_ADMIN,
    create_access_token,
    client_ip,
    get_authenticated_user,
    hash_password,
    require_principal,
    require_role,
)
from app.core.config import settings
from app.core.database import get_db
from app.core.rate_limit import rate_limit
from app.db.models import User
from app.schemas.auth import LoginRequest, RegisterRequest, TokenResponse, UserResponse
from app.services.audit_service import record_audit

router = APIRouter(prefix="/auth", tags=["auth"])

# Tighter rate limit on login to slow credential stuffing.
_login_rate_limit = rate_limit(name="auth_login", limit=10, window_seconds=60.0)
_register_rate_limit = rate_limit(name="auth_register", limit=20, window_seconds=300.0)


def _to_user_response(user: User) -> UserResponse:
    return UserResponse(id=user.id, email=user.email, role=user.role, is_active=user.is_active)


@router.post("/login", response_model=TokenResponse)
def login(
    payload: LoginRequest,
    request: Request,
    db: Session = Depends(get_db),
    _: None = Depends(_login_rate_limit),
):
    user = get_authenticated_user(db, email=payload.email, password=payload.password)
    if user is None:
        record_audit(db, action="auth.login.fail", target_type="email", target_id=payload.email, ip_address=client_ip(request))
        db.commit()
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials")
    token = create_access_token(user_id=user.id, role=user.role)
    record_audit(db, action="auth.login.ok", user_id=user.id, target_type="user", target_id=user.id, ip_address=client_ip(request))
    db.commit()
    return TokenResponse(
        access_token=token,
        expires_in_seconds=settings.jwt_ttl_minutes * 60,
        user=_to_user_response(user),
    )


@router.post("/register", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
def register(
    payload: RegisterRequest,
    request: Request,
    db: Session = Depends(get_db),
    _: None = Depends(_register_rate_limit),
):
    """Create a new user.

    Two access modes:
    - Bootstrap: if the users table is empty AND `ALLOW_FIRST_ADMIN_BOOTSTRAP=true`,
      anyone may create the first user, who is forced to role=admin. This lets a
      fresh deploy create the first admin without an existing token. Disabled in
      production by config validator.
    - Normal: caller must be authenticated as admin.
    """
    user_count = db.scalar(select(func.count(User.id))) or 0
    is_bootstrap = user_count == 0 and settings.allow_first_admin_bootstrap
    actor_user_id: int | None = None

    if is_bootstrap:
        forced_role = ROLE_ADMIN
    else:
        # Manually invoke the require_role dependency: we cannot use Depends here
        # because bootstrap mode must allow unauthenticated access.
        from app.core.auth import get_current_principal
        principal = get_current_principal(
            authorization=request.headers.get("authorization"),
            admin_api_key=request.headers.get("x-admin-api-key"),
            db=db,
        )
        if principal is None or principal.role != ROLE_ADMIN:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Only admin may create users")
        actor_user_id = principal.user_id
        forced_role = payload.role

    user = User(
        email=payload.email,
        password_hash=hash_password(payload.password),
        role=forced_role,
        is_active=True,
    )
    db.add(user)
    try:
        db.flush()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Email already registered")
    record_audit(
        db,
        action="auth.register",
        user_id=actor_user_id,
        target_type="user",
        target_id=user.id,
        detail={"created_email": user.email, "role": user.role, "bootstrap": is_bootstrap},
        ip_address=client_ip(request),
    )
    db.commit()
    return _to_user_response(user)


@router.get("/me", response_model=UserResponse)
def me(principal: AuthPrincipal = Depends(require_principal)):
    if principal.user is None:
        # Machine-key principal — synthesize a stable response.
        return UserResponse(id=0, email="machine@local", role=principal.role, is_active=True)
    return _to_user_response(principal.user)


@router.get("/users", response_model=list[UserResponse])
def list_users(
    db: Session = Depends(get_db),
    _: AuthPrincipal = Depends(require_role(ROLE_ADMIN)),
):
    users = db.scalars(select(User).order_by(User.id)).all()
    return [_to_user_response(u) for u in users]
