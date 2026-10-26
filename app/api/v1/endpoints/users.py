from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, status, Query, Request
from sqlalchemy.orm import Session
from sqlalchemy import or_
from sqlalchemy.exc import IntegrityError

from app.core.database import get_db
from app.core.security import get_password_hash
from app.models.user import User, UserRole, Administrator, CourtClerk, Judge, Lawyer, Litigant
from app.schemas.auth import UserCreate, UserProfileResponse, UserUpdateStatus
from app.api.deps import require_roles, get_current_active_user
from app.services.audit_service import AuditService
from app.api.v1.endpoints.auth import build_user_profile

router = APIRouter()

@router.post("", response_model=UserProfileResponse, status_code=status.HTTP_201_CREATED, summary="Create User Account (Admin Only)")
def create_user(
    user_in: UserCreate,
    request: Request = None,
    db: Session = Depends(get_db),
    current_admin: User = Depends(require_roles(UserRole.ADMINISTRATOR))
):
    """
    Administrator onboards a new judicial user and assigns role (FR-4.1.3 Authentication.Role.Assign).
    """
    client_ip = request.client.host if (request and request.client) else None

    # Check for existing email or username
    existing_user = db.query(User).filter(
        or_(User.username == user_in.username, User.email == user_in.email)
    ).first()
    if existing_user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="User with this username or email already exists."
        )

    if user_in.employee_id and db.query(CourtClerk).filter(CourtClerk.employee_id == user_in.employee_id).first():
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="This employee ID is already registered.")
    if user_in.bar_registration_no and db.query(Lawyer).filter(Lawyer.bar_registration_no == user_in.bar_registration_no).first():
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="This bar registration number is already registered.")

    hashed_pw = get_password_hash(user_in.password)

    # Instantiate concrete role subclass
    if user_in.role == UserRole.ADMINISTRATOR:
        user = Administrator(
            name=user_in.name,
            email=user_in.email,
            mobile_no=user_in.mobile_no,
            username=user_in.username,
            password=hashed_pw,
            role=UserRole.ADMINISTRATOR,
            admin_role=user_in.admin_role or "ADMIN"
        )
    elif user_in.role == UserRole.COURT_CLERK:
        if not user_in.employee_id:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="employee_id is required for Court Clerk")
        user = CourtClerk(
            name=user_in.name,
            email=user_in.email,
            mobile_no=user_in.mobile_no,
            username=user_in.username,
            password=hashed_pw,
            role=UserRole.COURT_CLERK,
            employee_id=user_in.employee_id
        )
    elif user_in.role == UserRole.JUDGE:
        user = Judge(
            name=user_in.name,
            email=user_in.email,
            mobile_no=user_in.mobile_no,
            username=user_in.username,
            password=hashed_pw,
            role=UserRole.JUDGE,
            specialization=user_in.specialization or "General",
            availability="Available"
        )
    elif user_in.role == UserRole.LAWYER:
        if not user_in.bar_registration_no:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="bar_registration_no is required for Lawyer")
        user = Lawyer(
            name=user_in.name,
            email=user_in.email,
            mobile_no=user_in.mobile_no,
            username=user_in.username,
            password=hashed_pw,
            role=UserRole.LAWYER,
            bar_registration_no=user_in.bar_registration_no
        )
    elif user_in.role == UserRole.LITIGANT:
        user = Litigant(
            name=user_in.name,
            email=user_in.email,
            mobile_no=user_in.mobile_no,
            username=user_in.username,
            password=hashed_pw,
            role=UserRole.LITIGANT,
            address=user_in.address or "Address not provided"
        )
    else:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Unsupported user role")

    db.add(user)
    try:
        db.commit()
        db.refresh(user)
    except IntegrityError:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="A user with one of these details is already registered. Check the username, email, employee ID, or bar registration number."
        )

    AuditService.log(
        db=db,
        action="USER_CREATED",
        entity_type="User",
        entity_id=str(user.user_id),
        user_id=current_admin.user_id,
        details=f"Admin {current_admin.username} created user {user.username} with role {user.role.value}",
        ip_address=client_ip
    )

    return build_user_profile(user)


@router.get("", response_model=List[UserProfileResponse], summary="List Users with Optional Role Filter")
def list_users(
    role: Optional[UserRole] = None,
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(UserRole.ADMINISTRATOR, UserRole.COURT_CLERK))
):
    """
    List registered judicial users. Accessible to Admins and Court Clerks.
    """
    query = db.query(User)
    if role:
        query = query.filter(User.role == role)
    
    limit_val = limit if isinstance(limit, int) else 50
    offset_val = offset if isinstance(offset, int) else 0

    users = query.order_by(User.created_at.desc()).offset(offset_val).limit(limit_val).all()
    return [build_user_profile(u) for u in users]


@router.put("/{user_id}/status", response_model=UserProfileResponse, summary="Activate / Deactivate User Account")
def update_user_status(
    user_id: int,
    status_update: UserUpdateStatus,
    request: Request = None,
    db: Session = Depends(get_db),
    current_admin: User = Depends(require_roles(UserRole.ADMINISTRATOR))
):
    """
    Administrator activates or deactivates user accounts (FR-4.1.3 Authentication.Account.Status).
    """
    client_ip = request.client.host if (request and request.client) else None
    user = db.query(User).filter(User.user_id == user_id).first()
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")

    user.is_active = status_update.is_active
    db.commit()
    db.refresh(user)

    AuditService.log(
        db=db,
        action="USER_STATUS_UPDATED",
        entity_type="User",
        entity_id=str(user.user_id),
        user_id=current_admin.user_id,
        details=f"Admin {current_admin.username} set user {user.username} is_active to {user.is_active}",
        ip_address=client_ip
    )

    return build_user_profile(user)


@router.get("/judges/available", summary="List Available Judges for Scheduling")
def list_available_judges(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """
    Helper endpoint returning list of active judges and their availability for scheduling.
    """
    judges = db.query(Judge).filter(Judge.is_active == True).all()
    return [
        {
            "judge_id": j.judge_id,
            "name": j.name,
            "email": j.email,
            "specialization": j.specialization,
            "availability": j.availability
        }
        for j in judges
    ]
