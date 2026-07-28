"""Append-only audit trail.

Every manual correction, approval and status change is recorded here. Rows are
inserted and never updated or deleted -- the history is the evidence that a
person reviewed what the model produced.
"""

from __future__ import annotations

import json
from decimal import Decimal
from datetime import date, datetime
from typing import Any

from sqlmodel import Session, select

from src.models import AuditEvent


def _encode(value: Any) -> str | None:
    """Serialise a value for storage, keeping Decimals exact as strings.

    Only structured field values are recorded here. Document contents and
    extracted personal information must never be written to the audit log.
    """
    if value is None:
        return None

    def default(obj: Any) -> str:
        if isinstance(obj, Decimal):
            return str(obj)
        if isinstance(obj, (datetime, date)):
            return obj.isoformat()
        return str(obj)

    return json.dumps(value, default=default, sort_keys=True)


def record(
    session: Session,
    *,
    event_type: str,
    record_type: str,
    record_id: int | None = None,
    summary: str = "",
    old_value: Any = None,
    new_value: Any = None,
) -> AuditEvent:
    """Append one event. The caller's session controls the transaction."""
    entry = AuditEvent(
        event_type=event_type,
        record_type=record_type,
        record_id=record_id,
        summary=summary,
        old_value_json=_encode(old_value),
        new_value_json=_encode(new_value),
    )
    session.add(entry)
    return entry


def recent(session: Session, limit: int = 50) -> list[AuditEvent]:
    statement = select(AuditEvent).order_by(AuditEvent.id.desc()).limit(limit)
    return list(session.exec(statement))
