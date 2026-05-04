from fastapi import Header, HTTPException, status

from app.core.config import settings


def require_admin_api_key(admin_api_key: str | None = Header(default=None, alias="X-Admin-API-Key")) -> None:
    if settings.admin_api_key is None:
        return
    if admin_api_key != settings.admin_api_key:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid admin API key")
