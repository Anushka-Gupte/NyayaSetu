from datetime import datetime
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, status, Request
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.orm import Session
from sqlalchemy import or_

from app.core.database import get_db
from app.core.security import verify_password, create_access_token, get_password_hash
from app.models.user import User, UserRole, Administrator, CourtClerk, Judge, Lawyer, Litigant
from app.schemas.auth import (
    TokenResponse,
    LoginRequest,
    UserProfileResponse,
    PasswordResetRequest,
    PasswordResetConfirm
)
from app.api.deps import get_current_active_user
from app.services.audit_service import AuditService

router = APIRouter()

def build_user_profile(user: User) -> UserProfileResponse:
    profile_data = {
        "user_id": user.user_id,
        "name": user.name,
        "email": user.email,
        "mobile_no": user.mobile_no,
        "username": user.username,
        "role": user.role,
        "is_active": user.is_active,
        "created_at": user.created_at,
    }
    
    # Enrich with role-specific attributes
    if isinstance(user, Administrator):
        profile_data["admin_role"] = user.admin_role
    elif isinstance(user, CourtClerk):
        profile_data["employee_id"] = user.employee_id
    elif isinstance(user, Judge):
        profile_data["specialization"] = user.specialization
        profile_data["availability"] = user.availability
    elif isinstance(user, Lawyer):
        profile_data["bar_registration_no"] = user.bar_registration_no
    elif isinstance(user, Litigant):
        profile_data["address"] = user.address

    return UserProfileResponse(**profile_data)


@router.post("/login", response_model=TokenResponse, summary="User Login (JSON)")
def login(
    login_data: LoginRequest,
    request: Request = None,
    db: Session = Depends(get_db)
):
    """
    Authenticate user with username or email and password.
    Records successful and unsuccessful login attempts in the audit log (FR-4.1.3).
    """
    client_ip = request.client.host if (request and request.client) else None

    user = db.query(User).filter(
        or_(User.username == login_data.username_or_email, User.email == login_data.username_or_email)
    ).first()

    if not user or not verify_password(login_data.password, user.password):
        # Audit failed login attempt
        AuditService.log(
            db=db,
            action="LOGIN_FAILED",
            entity_type="User",
            entity_id=str(user.user_id) if user else None,
            details=f"Failed login attempt for identifier: {login_data.username_or_email}",
            ip_address=client_ip
        )
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username/email or password",
            headers={"WWW-Authenticate": "Bearer"},
        )

    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User account is deactivated. Contact Court Administration."
        )

    # Generate JWT
    access_token = create_access_token(
        data={"sub": user.username, "role": user.role.value, "user_id": user.user_id}
    )

    # Audit successful login
    AuditService.log(
        db=db,
        action="LOGIN_SUCCESS",
        entity_type="User",
        entity_id=str(user.user_id),
        user_id=user.user_id,
        details=f"User {user.username} logged in with role {user.role.value}",
        ip_address=client_ip
    )

    return TokenResponse(
        access_token=access_token,
        token_type="bearer",
        user_id=user.user_id,
        name=user.name,
        email=user.email,
        username=user.username,
        role=user.role
    )


@router.post("/token", response_model=TokenResponse, summary="OAuth2 Form Login (Swagger UI)")
def login_form(
    form_data: OAuth2PasswordRequestForm = Depends(),
    request: Request = None,
    db: Session = Depends(get_db)
):
    """
    Standard OAuth2 password flow endpoint enabling direct authorization in Swagger docs (/docs).
    """
    return login(
        login_data=LoginRequest(username_or_email=form_data.username, password=form_data.password),
        request=request,
        db=db
    )


@router.get("/me", response_model=UserProfileResponse, summary="Get Current User Profile")
def get_me(current_user: User = Depends(get_current_active_user)):
    """
    View currently authenticated user's profile and role-specific judicial details.
    """
    return build_user_profile(current_user)


@router.post("/logout", summary="User Logout")
def logout(
    request: Request = None,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """
    Terminate active session and log logout in audit trail (FR-4.1.3).
    """
    client_ip = request.client.host if (request and request.client) else None
    AuditService.log(
        db=db,
        action="LOGOUT",
        entity_type="User",
        entity_id=str(current_user.user_id),
        user_id=current_user.user_id,
        details=f"User {current_user.username} logged out",
        ip_address=client_ip
    )
    return {"message": "Successfully logged out of NyayaSetu session."}


@router.post("/password-reset-request", summary="Request Password Reset")
def request_password_reset(
    req: PasswordResetRequest,
    db: Session = Depends(get_db)
):
    """
    Initiate password reset via registered email (FR-4.1.3).
    """
    user = db.query(User).filter(User.email == req.email).first()
    if not user:
        # Avoid user enumeration by returning standard response
        return {"message": "If this email is registered, password reset instructions have been generated."}

    # Generate reset token (in real production email is dispatched; here token is logged & acknowledged)
    reset_token = create_access_token(data={"sub": user.username, "type": "password_reset"})
    
    AuditService.log(
        db=db,
        action="PASSWORD_RESET_REQUESTED",
        entity_type="User",
        entity_id=str(user.user_id),
        user_id=user.user_id,
        details=f"Password reset requested for {user.email}"
    )

    return {
        "message": "Password reset instructions have been issued.",
        "reset_token_dev": reset_token # Provided for easy testing in development
    }


@router.post("/password-reset-confirm", summary="Confirm Password Reset")
def confirm_password_reset(
    req: PasswordResetConfirm,
    db: Session = Depends(get_db)
):
    """
    Complete password reset with new secure password.
    """
    from app.core.security import decode_access_token
    payload = decode_access_token(req.token)
    if not payload or payload.get("type") != "password_reset":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid or expired password reset token"
        )

    username = payload.get("sub")
    user = db.query(User).filter(User.username == username).first()
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")

    user.password = get_password_hash(req.new_password)
    db.commit()

    AuditService.log(
        db=db,
        action="PASSWORD_RESET_COMPLETED",
        entity_type="User",
        entity_id=str(user.user_id),
        user_id=user.user_id,
        details=f"Password reset successfully completed for user {user.username}"
    )

    return {"message": "Password has been successfully updated. You may now log in with your new credentials."}
