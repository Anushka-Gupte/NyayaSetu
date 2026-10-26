import os
from typing import List, Optional
from datetime import datetime, date, timedelta
from fastapi import APIRouter, Depends, HTTPException, status, Query, Request, Response
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.models.user import User, UserRole
from app.models.cause_list import CauseList
from app.models.hearing import Hearing
from app.models.case import CourtCase
from app.schemas.cause_list import (
    CauseListGenerateRequest,
    CauseListResponse,
    CauseListEntry,
    CalendarEventResponse
)
from app.api.deps import get_current_active_user, require_roles
from app.services.cause_list_service import CauseListService
from app.services.audit_service import AuditService
from app.services.ai_scheduler_service import AISchedulerService

router = APIRouter()

def build_cause_list_response(cl: CauseList, entries: List[CauseListEntry]) -> CauseListResponse:
    pdf_url = f"/api/v1/cause-lists/{cl.cause_list_id}/pdf" if cl.pdf_path else None
    return CauseListResponse(
        cause_list_id=cl.cause_list_id,
        date=cl.date,
        court_name=cl.court_name,
        is_published=cl.is_published,
        generated_date=cl.generated_date,
        published_at=cl.published_at,
        pdf_url=pdf_url,
        total_cases=len(entries),
        entries=entries
    )

@router.post("/generate", response_model=CauseListResponse, status_code=status.HTTP_201_CREATED, summary="Generate Daily Cause List")
def generate_cause_list(
    req: CauseListGenerateRequest,
    request: Request = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(UserRole.COURT_CLERK, UserRole.ADMINISTRATOR))
):
    """
    Automatically compiles and generates the daily cause list (FR-4.4.3 CauseList.Generate).
    Sorts by courtroom and hearing timings.
    """
    client_ip = request.client.host if (request and request.client) else None

    # Check if a cause list already exists for this date
    existing_cl = db.query(CauseList).filter(CauseList.date == req.date).first()
    
    entries = CauseListService.get_cause_list_entries(db, req.date)

    if existing_cl:
        # Update existing record
        cause_list = existing_cl
        cause_list.court_name = req.court_name
        cause_list.generated_date = datetime.utcnow()
    else:
        cause_list = CauseList(
            date=req.date,
            court_name=req.court_name,
            is_published=False,
            generated_date=datetime.utcnow()
        )
        db.add(cause_list)
        db.flush()

    # Generate initial PDF document
    pdf_path = CauseListService.generate_pdf(
        cause_list_id=cause_list.cause_list_id,
        target_date=req.date,
        court_name=req.court_name,
        entries=entries
    )
    cause_list.pdf_path = pdf_path

    # Associate court cases scheduled on this date with this cause list
    hearing_case_ids = db.query(Hearing.case_id).filter(
        Hearing.hearing_date == req.date,
        Hearing.hearing_status != "Cancelled"
    ).all()
    for (cid,) in hearing_case_ids:
        c = db.query(CourtCase).filter(CourtCase.case_id == cid).first()
        if c:
            c.cause_list_id = cause_list.cause_list_id

    db.commit()
    db.refresh(cause_list)

    AuditService.log(
        db=db,
        action="CAUSE_LIST_GENERATED",
        entity_type="CauseList",
        entity_id=str(cause_list.cause_list_id),
        user_id=current_user.user_id,
        details=f"Cause List #{cause_list.cause_list_id} generated for {req.date} ({len(entries)} matters)",
        ip_address=client_ip
    )

    return build_cause_list_response(cause_list, entries)


@router.get("", response_model=List[CauseListResponse], summary="List Cause Lists")
def list_cause_lists(
    date_from: Optional[date] = None,
    date_to: Optional[date] = None,
    limit: int = Query(30, ge=1, le=100),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """
    List all generated or published daily cause lists (FR-4.4.3 CauseList.View).
    """
    query = db.query(CauseList)
    if date_from:
        query = query.filter(CauseList.date >= date_from)
    if date_to:
        query = query.filter(CauseList.date <= date_to)

    # Litigants only see published cause lists
    if current_user.role == UserRole.LITIGANT:
        query = query.filter(CauseList.is_published == True)

    limit_val = limit if isinstance(limit, int) else 30
    offset_val = offset if isinstance(offset, int) else 0

    cause_lists = query.order_by(CauseList.date.desc()).offset(offset_val).limit(limit_val).all()
    
    res = []
    for cl in cause_lists:
        entries = CauseListService.get_cause_list_entries(db, cl.date)
        res.append(build_cause_list_response(cl, entries))
    return res


@router.get("/{cause_list_id}", response_model=CauseListResponse, summary="Get Cause List Details")
def get_cause_list_details(
    cause_list_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """
    Retrieves full cause list entry breakdown for a specific date.
    """
    cl = db.query(CauseList).filter(CauseList.cause_list_id == cause_list_id).first()
    if not cl:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Cause list not found")

    if not cl.is_published and current_user.role == UserRole.LITIGANT:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Cause list has not been published yet")

    entries = CauseListService.get_cause_list_entries(db, cl.date)
    return build_cause_list_response(cl, entries)


@router.put("/{cause_list_id}/publish", response_model=CauseListResponse, summary="Publish Cause List")
def publish_cause_list(
    cause_list_id: int,
    request: Request = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(UserRole.COURT_CLERK, UserRole.ADMINISTRATOR))
):
    """
    Publishes the finalized cause list, making it visible to the public and litigants (FR-4.4.3 CauseList.Publish).
    """
    client_ip = request.client.host if (request and request.client) else None
    cl = db.query(CauseList).filter(CauseList.cause_list_id == cause_list_id).first()
    if not cl:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Cause list not found")

    entries = CauseListService.get_cause_list_entries(db, cl.date)

    # Re-generate finalized PDF upon publication to ensure all latest modifications are reflected (BR-5.7)
    pdf_path = CauseListService.generate_pdf(
        cause_list_id=cl.cause_list_id,
        target_date=cl.date,
        court_name=cl.court_name,
        entries=entries
    )

    cl.is_published = True
    cl.published_at = datetime.utcnow()
    cl.pdf_path = pdf_path
    db.commit()
    db.refresh(cl)

    AuditService.log(
        db=db,
        action="CAUSE_LIST_PUBLISHED",
        entity_type="CauseList",
        entity_id=str(cl.cause_list_id),
        user_id=current_user.user_id,
        details=f"Cause List #{cl.cause_list_id} published for {cl.date}",
        ip_address=client_ip
    )

    return build_cause_list_response(cl, entries)


@router.get("/{cause_list_id}/pdf", summary="Download Cause List PDF")
def download_cause_list_pdf(
    cause_list_id: int,
    request: Request = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """
    Downloads printable Daily Cause List in PDF format (FR-4.4.3 CauseList.Download).
    """
    client_ip = request.client.host if (request and request.client) else None
    cl = db.query(CauseList).filter(CauseList.cause_list_id == cause_list_id).first()
    if not cl:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Cause list not found")

    if not cl.is_published and current_user.role == UserRole.LITIGANT:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Draft cause list is not available for download")

    if not cl.pdf_path or not os.path.exists(cl.pdf_path):
        # Generate on demand
        entries = CauseListService.get_cause_list_entries(db, cl.date)
        cl.pdf_path = CauseListService.generate_pdf(cl.cause_list_id, cl.date, cl.court_name, entries)
        db.commit()

    AuditService.log(
        db=db,
        action="CAUSE_LIST_DOWNLOADED",
        entity_type="CauseList",
        entity_id=str(cl.cause_list_id),
        user_id=current_user.user_id,
        details=f"Cause List PDF #{cl.cause_list_id} downloaded by {current_user.username}",
        ip_address=client_ip
    )

    filename = os.path.basename(cl.pdf_path)
    return FileResponse(
        path=cl.pdf_path,
        filename=filename,
        media_type="application/pdf"
    )


# ==============================================================================
# Calendar Synchronization Endpoints (SRS Section 4.4 & Calendar class)
# ==============================================================================

@router.get("/calendar/events", response_model=List[CalendarEventResponse], summary="Get Court Calendar Events")
def get_calendar_events(
    date_from: Optional[date] = None,
    date_to: Optional[date] = None,
    judge_id: Optional[int] = None,
    courtroom_id: Optional[int] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """
    Returns calendar events for interactive judicial calendar views with filtering (FR-4.4.3 Calendar.View, Calendar.Filter).
    """
    query = db.query(Hearing).filter(Hearing.hearing_status != "Cancelled")

    if date_from:
        query = query.filter(Hearing.hearing_date >= date_from)
    if date_to:
        query = query.filter(Hearing.hearing_date <= date_to)
    if judge_id:
        query = query.filter(Hearing.judge_id == judge_id)
    if courtroom_id:
        query = query.filter(Hearing.courtroom_id == courtroom_id)

    # Scoping for Judge / Litigant
    if current_user.role == UserRole.JUDGE:
        query = query.filter(Hearing.judge_id == current_user.user_id)
    elif current_user.role == UserRole.LITIGANT:
        query = query.join(CourtCase, Hearing.case_id == CourtCase.case_id).filter(
            CourtCase.litigant_id == current_user.user_id
        )

    hearings = query.order_by(Hearing.hearing_date.asc(), Hearing.hearing_time.asc()).all()

    events: List[CalendarEventResponse] = []
    for h in hearings:
        c = h.case
        start_time_str = AISchedulerService.format_time_obj(h.hearing_time)
        dt_start = datetime.combine(h.hearing_date, h.hearing_time)
        dt_end = dt_start + timedelta(minutes=45)
        end_time_str = dt_end.time().strftime("%H:%M")

        events.append(CalendarEventResponse(
            event_id=f"EVT-{h.hearing_id}",
            hearing_id=h.hearing_id,
            case_id=h.case_id,
            case_number=c.case_number if c else f"Case #{h.case_id}",
            title=c.title if c else "Case details unavailable",
            hearing_date=h.hearing_date,
            start_time=start_time_str,
            end_time=end_time_str,
            courtroom_name=h.courtroom.courtroom_name if h.courtroom else "Not allocated",
            judge_name=h.judge.name if h.judge else "Not assigned",
            hearing_type=h.hearing_type,
            status=h.hearing_status
        ))

    return events


@router.get("/calendar/export.ics", summary="Export iCalendar (.ics) Feed for Google / Outlook Sync")
def export_ical_feed(
    judge_id: Optional[int] = None,
    courtroom_id: Optional[int] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """
    Exports calendar sync feed in RFC 5545 iCalendar standard format for Google Calendar, Outlook, and Apple Calendar (FR-4.4.3 Calendar.Sync).
    """
    query = db.query(Hearing).filter(Hearing.hearing_status != "Cancelled")
    if judge_id:
        query = query.filter(Hearing.judge_id == judge_id)
    if courtroom_id:
        query = query.filter(Hearing.courtroom_id == courtroom_id)

    hearings = query.all()
    ics_text = CauseListService.generate_ics_feed(hearings, court_name="NyayaSetu Judicial Court")

    return Response(
        content=ics_text,
        media_type="text/calendar",
        headers={"Content-Disposition": "attachment; filename=nyayasetu_court_calendar.ics"}
    )
