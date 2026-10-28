from datetime import datetime
from typing import Generator, List, Optional
from fastapi import Depends, HTTPException, Query, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.orm import Session
from app.core.database import get_db
from app.core.security import decode_access_token
from app.models.user import User, UserRole
from app.models.audit import AuditLog

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/login", auto_error=False)

def get_current_user(
    db: Session = Depends(get_db),
    token_header: Optional[str] = Depends(oauth2_scheme),
    token_query: Optional[str] = Query(None, alias="token"),
) -> User:
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )

    token = token_header or token_query
    if not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    payload = decode_access_token(token)
    if not payload or payload.get("type") == "password_reset":
        raise credentials_exception
        
    username: str = payload.get("sub")
    if not username:
        raise credentials_exception
        
    user = db.query(User).filter(User.username == username).first()
    if not user:
        raise credentials_exception

    issued_at = payload.get("iat")
    if not issued_at:
        raise credentials_exception
    invalidation_event = db.query(AuditLog).filter(
        AuditLog.user_id == user.user_id,
        AuditLog.action.in_(["LOGOUT", "PASSWORD_RESET_COMPLETED"])
    ).order_by(AuditLog.date_time.desc()).first()
    if invalidation_event and datetime.utcfromtimestamp(issued_at) <= invalidation_event.date_time:
        raise credentials_exception
        
    return user

def get_current_user_optional(
    db: Session = Depends(get_db),
    token_header: Optional[str] = Depends(oauth2_scheme),
    token_query: Optional[str] = Query(None, alias="token"),
) -> Optional[User]:
    token = token_header or token_query
    if not token:
        return None
    try:
        payload = decode_access_token(token)
        if not payload or payload.get("type") == "password_reset":
            return None
        username: str = payload.get("sub")
        if not username:
            return None
        user = db.query(User).filter(User.username == username).first()
        if not user or not user.is_active:
            return None
        issued_at = payload.get("iat")
        if not issued_at:
            return None
        invalidation_event = db.query(AuditLog).filter(
            AuditLog.user_id == user.user_id,
            AuditLog.action.in_(["LOGOUT", "PASSWORD_RESET_COMPLETED"])
        ).order_by(AuditLog.date_time.desc()).first()
        if invalidation_event and datetime.utcfromtimestamp(issued_at) <= invalidation_event.date_time:
            return None
        return user
    except Exception:
        return None

def get_current_active_user(
    current_user: User = Depends(get_current_user)
) -> User:
    if not current_user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Inactive user account"
        )
    return current_user

def require_roles(*allowed_roles: UserRole):
    """
    Enforces Role-Based Access Control (RBAC).
    Matches SRS NFR-5.3.2 and Authentication.Role.Access.
    """
    def role_checker(current_user: User = Depends(get_current_active_user)) -> User:
        if current_user.role not in allowed_roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Access denied: Insufficient permissions for role '{current_user.role.value}'"
            )
        return current_user
    return role_checker
