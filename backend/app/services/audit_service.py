"""Audit log writes. Best-effort: a failure to log MUST NOT break the request,
but it MUST be logged to stderr so ops can detect the gap."""
from __future__ import annotations

import logging
from typing import Any

from sqlalchemy.orm import Session

from app.db.models import AuditLogEntry

logger = logging.getLogger(__name__)


def record_audit(
    db: Session,
    *,
    action: str,
    user_id: int | None = None,
    target_type: str | None = None,
    target_id: str | int | None = None,
    detail: dict[str, Any] | None = None,
    ip_address: str | None = None,
) -> None:
    try:
        entry = AuditLogEntry(
            user_id=user_id,
            action=action,
            target_type=target_type,
            target_id=str(target_id) if target_id is not None else None,
            detail_json=detail,
            ip_address=ip_address,
        )
        db.add(entry)
        db.flush()
    except Exception:
        logger.exception("audit_log write failed action=%s target=%s", action, target_id)
