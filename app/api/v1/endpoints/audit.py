from typing import List, Optional
from datetime import datetime
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from pydantic import BaseModel

from app.core.database import get_db
from app.models.user import User, UserRole
from app.models.audit import AuditLog
from app.api.deps import require_roles

router = APIRouter()

class AuditLogResponse(BaseModel):
    log_id: int
    user_id: Optional[int]
    action: str
    entity_type: str
    entity_id: Optional[str]
    details: Optional[str]
    ip_address: Optional[str]
    date_time: datetime

    class Config:
        from_attributes = True

@router.get("", response_model=List[AuditLogResponse], summary="View Audit Logs (Admin Only)")
def list_audit_logs(
    action: Optional[str] = None,
    entity_type: Optional[str] = None,
    user_id: Optional[int] = None,
    limit: int = Query(50, ge=1, le=500),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
    current_admin: User = Depends(require_roles(UserRole.ADMINISTRATOR))
):
    """
    View immutable judicial audit trails. Strictly restricted to Administrators (SRS NFR-5.3.7 & NFR-5.3.8).
    """
    query = db.query(AuditLog)
    if action:
        query = query.filter(AuditLog.action == action)
    if entity_type:
        query = query.filter(AuditLog.entity_type == entity_type)
    if user_id:
        query = query.filter(AuditLog.user_id == user_id)

    limit_val = limit if isinstance(limit, int) else 50
    offset_val = offset if isinstance(offset, int) else 0

    logs = query.order_by(AuditLog.date_time.desc()).offset(offset_val).limit(limit_val).all()
    return logs
