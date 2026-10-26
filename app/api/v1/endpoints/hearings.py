from typing import List, Optional
from datetime import datetime, date, time
from fastapi import APIRouter, Depends, HTTPException, status, Query, Request
from sqlalchemy.orm import Session
from sqlalchemy import or_
from sqlalchemy.exc import IntegrityError

from app.core.database import get_db
from app.models.user import User, UserRole, Judge
from app.models.hearing import Hearing, Courtroom
from app.models.case import CourtCase, CaseHistory
from app.schemas.hearing import (
    HearingRecommendationRequest,
    HearingRecommendationResponse,
    HearingSlotRecommendation,
    HearingScheduleCreate,
    HearingRescheduleRequest,
    HearingCancelRequest,
    HearingAdjournRequest,
    HearingCompleteRequest,
    ConflictCheckRequest,
    ConflictCheckResponse,
    HearingResponse,
    CourtroomCreate,
    CourtroomResponse
)
from app.api.deps import get_current_active_user, require_roles
from app.services.ai_scheduler_service import AISchedulerService
from app.services.audit_service import AuditService

router = APIRouter()

def build_hearing_response(h: Hearing) -> HearingResponse:
    judge_name = h.judge.name if h.judge else f"Judge #{h.judge_id}"
    courtroom_name = h.courtroom.courtroom_name if h.courtroom else f"Courtroom #{h.courtroom_id}"
    courtroom_loc = h.courtroom.location if h.courtroom else ""
    case_num = h.case.case_number if h.case else f"Case #{h.case_id}"
    case_title = h.case.title if h.case else ""

    return HearingResponse(
        hearing_id=h.hearing_id,
        case_id=h.case_id,
        case_number=case_num,
        case_title=case_title,
        judge_id=h.judge_id,
        judge_name=judge_name,
        courtroom_id=h.courtroom_id,
        courtroom_name=courtroom_name,
        courtroom_location=courtroom_loc,
        hearing_date=h.hearing_date,
        hearing_time=AISchedulerService.format_time_obj(h.hearing_time),
        hearing_status=h.hearing_status,
        hearing_type=h.hearing_type,
        adjournment_reason=h.adjournment_reason,
        outcome=h.outcome,
        created_at=h.created_at
    )


@router.post("/recommend", response_model=HearingRecommendationResponse, summary="Generate AI Hearing Recommendations")
def get_ai_recommendations(
    req: HearingRecommendationRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(UserRole.COURT_CLERK, UserRole.ADMINISTRATOR))
):
    """
    AI-Powered hearing scheduling recommendation engine (FR-4.3.3 Scheduling.AI.Recommend).
    Optimizes for judge specialization, courtroom availability, case priority, and workload balance.
    """
    case = db.query(CourtCase).filter(CourtCase.case_id == req.case_id).first()
    if not case:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Case not found")

    recs = AISchedulerService.generate_recommendations(
        db=db,
        case_id=case.case_id,
        days_ahead_start=req.days_ahead_start,
        days_ahead_end=req.days_ahead_end
    )

    return HearingRecommendationResponse(
        case_id=case.case_id,
        case_number=case.case_number,
        case_title=case.title,
        case_type=case.case_type,
        priority=case.priority,
        recommendations=recs
    )


@router.post("/check-conflict", response_model=ConflictCheckResponse, summary="Detect Scheduling Conflicts")
def check_conflicts(
    check: ConflictCheckRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """
    Detects scheduling conflicts for judge, courtroom, advocate, and court calendar (FR-4.3.3 Scheduling.Conflict.Detect).
    """
    conflicts = AISchedulerService.detect_conflicts(
        db=db,
        case_id=check.case_id,
        judge_id=check.judge_id,
        courtroom_id=check.courtroom_id,
        hearing_date=check.hearing_date,
        hearing_time_str=check.hearing_time,
        exclude_hearing_id=check.exclude_hearing_id
    )

    alternatives = []
    if conflicts:
        alternatives = AISchedulerService.generate_recommendations(
            db=db, case_id=check.case_id, max_recommendations=3
        )

    return ConflictCheckResponse(
        has_conflict=len(conflicts) > 0,
        conflicts=conflicts,
        suggested_alternatives=alternatives
    )


@router.post("", response_model=HearingResponse, status_code=status.HTTP_201_CREATED, summary="Schedule Hearing")
def schedule_hearing(
    schedule_in: HearingScheduleCreate,
    request: Request = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(UserRole.COURT_CLERK, UserRole.ADMINISTRATOR))
):
    """
    Schedules a new court hearing (FR-4.3.3 Scheduling.Create).
    Verifies conflict avoidance and records judicial resource allocations.
    """
    client_ip = request.client.host if (request and request.client) else None

    case = db.query(CourtCase).filter(CourtCase.case_id == schedule_in.case_id).first()
    if not case:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Case not found")

    judge = db.query(Judge).filter(Judge.judge_id == schedule_in.judge_id).first()
    if not judge:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Judge not found")

    courtroom = db.query(Courtroom).filter(Courtroom.courtroom_id == schedule_in.courtroom_id).first()
    if not courtroom:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Courtroom not found")

    # Strict conflict verification (BR-5.3)
    conflicts = AISchedulerService.detect_conflicts(
        db=db,
        case_id=schedule_in.case_id,
        judge_id=schedule_in.judge_id,
        courtroom_id=schedule_in.courtroom_id,
        hearing_date=schedule_in.hearing_date,
        hearing_time_str=schedule_in.hearing_time
    )
    if conflicts:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Scheduling conflict detected: {'; '.join(conflicts)}"
        )

    parsed_time = AISchedulerService.parse_time_str(schedule_in.hearing_time)

    hearing = Hearing(
        case_id=schedule_in.case_id,
        judge_id=schedule_in.judge_id,
        courtroom_id=schedule_in.courtroom_id,
        hearing_date=schedule_in.hearing_date,
        hearing_time=parsed_time,
        hearing_status="Scheduled",
        hearing_type=schedule_in.hearing_type
    )
    db.add(hearing)

    # Automatically move case status to Active if it was Registered
    if case.case_status == "Registered":
        case.case_status = "Active"

    # Add Case History record
    method_tag = " (AI Recommended)" if schedule_in.is_ai_recommended else " (Manual Assignment)"
    history_entry = CaseHistory(
        case_id=case.case_id,
        event="HEARING_SCHEDULED",
        date_time=datetime.utcnow(),
        description=f"Hearing scheduled on {hearing.hearing_date} at {schedule_in.hearing_time} in {courtroom.courtroom_name} before {judge.name}{method_tag}.",
        user_id=current_user.user_id
    )
    db.add(history_entry)
    db.commit()
    db.refresh(hearing)

    # Audit Trail
    AuditService.log(
        db=db,
        action="HEARING_SCHEDULED",
        entity_type="Hearing",
        entity_id=str(hearing.hearing_id),
        user_id=current_user.user_id,
        details=f"Hearing #{hearing.hearing_id} scheduled for Case {case.case_number} on {hearing.hearing_date} at {schedule_in.hearing_time}",
        ip_address=client_ip
    )

    return build_hearing_response(hearing)


@router.get("", response_model=List[HearingResponse], summary="List Hearings with Filtering")
def list_hearings(
    case_id: Optional[int] = None,
    judge_id: Optional[int] = None,
    courtroom_id: Optional[int] = None,
    hearing_date: Optional[date] = None,
    status: Optional[str] = None,
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """
    List hearings with flexible date, judge, courtroom, and status filtering.
    """
    query = db.query(Hearing)

    # Role scoping for judge, lawyer, litigant
    if current_user.role == UserRole.JUDGE:
        query = query.filter(Hearing.judge_id == current_user.user_id)
    elif current_user.role == UserRole.LITIGANT:
        query = query.join(CourtCase, Hearing.case_id == CourtCase.case_id).filter(
            CourtCase.litigant_id == current_user.user_id
        )

    if case_id:
        query = query.filter(Hearing.case_id == case_id)
    if judge_id:
        query = query.filter(Hearing.judge_id == judge_id)
    if courtroom_id:
        query = query.filter(Hearing.courtroom_id == courtroom_id)
    if hearing_date:
        query = query.filter(Hearing.hearing_date == hearing_date)
    if status:
        query = query.filter(Hearing.hearing_status == status)

    limit_val = limit if isinstance(limit, int) else 50
    offset_val = offset if isinstance(offset, int) else 0

    hearings = query.order_by(Hearing.hearing_date.asc(), Hearing.hearing_time.asc()).offset(offset_val).limit(limit_val).all()
    return [build_hearing_response(h) for h in hearings]


@router.get("/{hearing_id}", response_model=HearingResponse, summary="Get Hearing Details")
def get_hearing(
    hearing_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """
    Returns single hearing proceeding record.
    """
    hearing = db.query(Hearing).filter(Hearing.hearing_id == hearing_id).first()
    if not hearing:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Hearing not found")
    return build_hearing_response(hearing)


@router.put("/{hearing_id}/reschedule", response_model=HearingResponse, summary="Reschedule Hearing")
def reschedule_hearing(
    hearing_id: int,
    reschedule_in: HearingRescheduleRequest,
    request: Request = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(UserRole.COURT_CLERK, UserRole.ADMINISTRATOR))
):
    """
    Reschedules an existing hearing to a new date, time, judge, or courtroom (FR-4.3.3 Scheduling.Reschedule).
    """
    client_ip = request.client.host if (request and request.client) else None
    hearing = db.query(Hearing).filter(Hearing.hearing_id == hearing_id).first()
    if not hearing:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Hearing not found")

    target_judge_id = reschedule_in.new_judge_id or hearing.judge_id
    target_courtroom_id = reschedule_in.new_courtroom_id or hearing.courtroom_id

    # Conflict check
    conflicts = AISchedulerService.detect_conflicts(
        db=db,
        case_id=hearing.case_id,
        judge_id=target_judge_id,
        courtroom_id=target_courtroom_id,
        hearing_date=reschedule_in.new_date,
        hearing_time_str=reschedule_in.new_time,
        exclude_hearing_id=hearing.hearing_id
    )
    if conflicts:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Rescheduling conflict detected: {'; '.join(conflicts)}"
        )

    old_date = hearing.hearing_date
    old_time = AISchedulerService.format_time_obj(hearing.hearing_time)

    hearing.hearing_date = reschedule_in.new_date
    hearing.hearing_time = AISchedulerService.parse_time_str(reschedule_in.new_time)
    hearing.judge_id = target_judge_id
    hearing.courtroom_id = target_courtroom_id
    hearing.hearing_status = "Scheduled"

    # History
    history_entry = CaseHistory(
        case_id=hearing.case_id,
        event="HEARING_RESCHEDULED",
        date_time=datetime.utcnow(),
        description=f"Hearing #{hearing.hearing_id} rescheduled from {old_date} {old_time} to {hearing.hearing_date} {reschedule_in.new_time}. Reason: {reschedule_in.reason}",
        user_id=current_user.user_id
    )
    db.add(history_entry)
    db.commit()
    db.refresh(hearing)

    AuditService.log(
        db=db,
        action="HEARING_RESCHEDULED",
        entity_type="Hearing",
        entity_id=str(hearing.hearing_id),
        user_id=current_user.user_id,
        details=f"Hearing #{hearing.hearing_id} rescheduled. Reason: {reschedule_in.reason}",
        ip_address=client_ip
    )

    return build_hearing_response(hearing)


@router.put("/{hearing_id}/cancel", response_model=HearingResponse, summary="Cancel Hearing")
def cancel_hearing(
    hearing_id: int,
    cancel_in: HearingCancelRequest,
    request: Request = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(UserRole.COURT_CLERK, UserRole.ADMINISTRATOR))
):
    """
    Cancels a scheduled hearing and releases judicial resources (FR-4.3.3 Scheduling.Cancel).
    """
    client_ip = request.client.host if (request and request.client) else None
    hearing = db.query(Hearing).filter(Hearing.hearing_id == hearing_id).first()
    if not hearing:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Hearing not found")

    hearing.hearing_status = "Cancelled"
    hearing.adjournment_reason = f"Cancelled: {cancel_in.reason}"

    history_entry = CaseHistory(
        case_id=hearing.case_id,
        event="HEARING_CANCELLED",
        date_time=datetime.utcnow(),
        description=f"Hearing #{hearing.hearing_id} cancelled. Reason: {cancel_in.reason}",
        user_id=current_user.user_id
    )
    db.add(history_entry)
    db.commit()
    db.refresh(hearing)

    AuditService.log(
        db=db,
        action="HEARING_CANCELLED",
        entity_type="Hearing",
        entity_id=str(hearing.hearing_id),
        user_id=current_user.user_id,
        details=f"Hearing #{hearing.hearing_id} cancelled. Reason: {cancel_in.reason}",
        ip_address=client_ip
    )

    return build_hearing_response(hearing)


@router.put("/{hearing_id}/adjourn", response_model=HearingResponse, summary="Adjourn Hearing")
def adjourn_hearing(
    hearing_id: int,
    adjourn_in: HearingAdjournRequest,
    request: Request = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(UserRole.JUDGE, UserRole.COURT_CLERK, UserRole.ADMINISTRATOR))
):
    """
    Adjourns hearing and records reason and next target date (FR-4.7.3 Tracking.Hearing.Adjourn).
    """
    client_ip = request.client.host if (request and request.client) else None
    hearing = db.query(Hearing).filter(Hearing.hearing_id == hearing_id).first()
    if not hearing:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Hearing not found")

    hearing.hearing_status = "Adjourned"
    hearing.adjournment_reason = adjourn_in.reason

    history_desc = f"Hearing #{hearing.hearing_id} adjourned. Reason: {adjourn_in.reason}."
    if adjourn_in.next_hearing_date:
        history_desc += f" Next hearing proposed on {adjourn_in.next_hearing_date}."

    history_entry = CaseHistory(
        case_id=hearing.case_id,
        event="HEARING_ADJOURNED",
        date_time=datetime.utcnow(),
        description=history_desc,
        user_id=current_user.user_id
    )
    db.add(history_entry)
    db.commit()
    db.refresh(hearing)

    AuditService.log(
        db=db,
        action="HEARING_ADJOURNED",
        entity_type="Hearing",
        entity_id=str(hearing.hearing_id),
        user_id=current_user.user_id,
        details=f"Hearing #{hearing.hearing_id} adjourned: {adjourn_in.reason}",
        ip_address=client_ip
    )

    return build_hearing_response(hearing)


@router.put("/{hearing_id}/complete", response_model=HearingResponse, summary="Complete Hearing")
def complete_hearing(
    hearing_id: int,
    complete_in: HearingCompleteRequest,
    request: Request = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(UserRole.JUDGE, UserRole.COURT_CLERK, UserRole.ADMINISTRATOR))
):
    """
    Marks ongoing hearing as Completed with judicial outcome recorded (FR-4.7.3 Tracking.Hearing.Complete).
    """
    client_ip = request.client.host if (request and request.client) else None
    hearing = db.query(Hearing).filter(Hearing.hearing_id == hearing_id).first()
    if not hearing:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Hearing not found")

    hearing.hearing_status = "Completed"
    hearing.outcome = complete_in.outcome

    history_entry = CaseHistory(
        case_id=hearing.case_id,
        event="HEARING_COMPLETED",
        date_time=datetime.utcnow(),
        description=f"Hearing #{hearing.hearing_id} completed. Order/Outcome: {complete_in.outcome}",
        user_id=current_user.user_id
    )
    db.add(history_entry)
    db.commit()
    db.refresh(hearing)

    AuditService.log(
        db=db,
        action="HEARING_COMPLETED",
        entity_type="Hearing",
        entity_id=str(hearing.hearing_id),
        user_id=current_user.user_id,
        details=f"Hearing #{hearing.hearing_id} completed. Outcome: {complete_in.outcome}",
        ip_address=client_ip
    )

    return build_hearing_response(hearing)


@router.get("/courtrooms/available", response_model=List[CourtroomResponse], summary="List Courtrooms")
def list_courtrooms(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """
    Returns courtrooms and capacity for judicial resource allocation.
    """
    courtrooms = db.query(Courtroom).all()
    return [CourtroomResponse.model_validate(c) for c in courtrooms]


@router.post("/courtrooms", response_model=CourtroomResponse, status_code=status.HTTP_201_CREATED, summary="Register Courtroom (Administrator)")
def create_courtroom(
    courtroom_in: CourtroomCreate,
    request: Request = None,
    db: Session = Depends(get_db),
    current_admin: User = Depends(require_roles(UserRole.ADMINISTRATOR))
):
    """Add an actual courtroom record supplied by court administration."""
    existing = db.query(Courtroom).filter(Courtroom.courtroom_name == courtroom_in.courtroom_name).first()
    if existing:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="A courtroom with this name already exists.")

    courtroom = Courtroom(
        courtroom_name=courtroom_in.courtroom_name,
        location=courtroom_in.location,
        capacity=courtroom_in.capacity,
        availability=True
    )
    db.add(courtroom)
    try:
        db.commit()
        db.refresh(courtroom)
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="A courtroom with this name already exists.")

    AuditService.log(
        db=db,
        action="COURTROOM_CREATED",
        entity_type="Courtroom",
        entity_id=str(courtroom.courtroom_id),
        user_id=current_admin.user_id,
        details=f"Courtroom {courtroom.courtroom_name} registered by {current_admin.username}",
        ip_address=request.client.host if (request and request.client) else None
    )
    return CourtroomResponse.model_validate(courtroom)
