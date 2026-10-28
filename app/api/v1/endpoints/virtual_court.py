import os
from typing import List, Optional
from datetime import datetime, date
from urllib.parse import urlparse
from fastapi import APIRouter, Depends, HTTPException, status, Query, Request, Response
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.database import get_db
from app.models.user import User, UserRole
from app.models.hearing import Hearing, OnlineHearing, Transcript, HearingAttendance
from app.schemas.virtual_court import (
    OnlineHearingCreate,
    OnlineHearingResponse,
    AttendanceRecordResponse,
    TranscriptResponse,
    JoinHearingResponse
)
from app.api.deps import get_current_active_user, require_roles
from app.services.virtual_court_service import VirtualCourtService
from app.services.google_meet_service import GoogleMeetService
from app.services.audit_service import AuditService

router = APIRouter()

def build_online_hearing_response(oh: OnlineHearing) -> OnlineHearingResponse:
    h = oh.hearing
    case = h.case if h else None
    attendees_count = len(oh.attendees) if oh.attendees else 0
    transcript_id = oh.transcript.transcript_id if oh.transcript else None

    return OnlineHearingResponse(
        online_hearing_id=oh.online_hearing_id,
        hearing_id=oh.hearing_id,
        case_number=case.case_number if case else "Case details unavailable",
        case_title=case.title if case else "Judicial Matter",
        meeting_link=oh.meeting_link,
        meeting_passcode=oh.meeting_passcode,
        meeting_provider=oh.meeting_provider,
        start_time=oh.start_time,
        end_time=oh.end_time,
        is_recorded=oh.is_recorded,
        recording_file_path=oh.recording_file_path,
        attendees_count=attendees_count,
        has_transcript=oh.transcript is not None,
        transcript_id=transcript_id
    )


def get_authorized_online_hearing(
    online_hearing_id: int,
    db: Session,
    current_user: User
) -> OnlineHearing:
    """Load a session only for a participant assigned to its hearing."""
    online_hearing = db.query(OnlineHearing).filter(
        OnlineHearing.online_hearing_id == online_hearing_id
    ).first()
    if not online_hearing:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Virtual hearing session not found")
    if not online_hearing.hearing or not VirtualCourtService.verify_participant_access(
        db, current_user, online_hearing.hearing
    ):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="You are not assigned to this hearing")
    return online_hearing

@router.post("/sessions", response_model=OnlineHearingResponse, status_code=status.HTTP_201_CREATED, summary="Create Virtual Courtroom Session")
def create_virtual_session(
    session_in: OnlineHearingCreate,
    request: Request = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """
    Creates or retrieves a secure virtual hearing link and session room (FR-4.6.3 VirtualHearing.Link.Generate).
    Accessible by court staff and all authorized hearing participants (Judge, Litigant, Assigned Advocates).
    """
    client_ip = request.client.host if (request and request.client) else None

    hearing = db.query(Hearing).filter(Hearing.hearing_id == session_in.hearing_id).first()
    if not hearing:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Hearing not found")

    # Verify that the current user has access to this hearing
    if not VirtualCourtService.verify_participant_access(db, current_user, hearing):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access Denied: You are not authorized for this hearing."
        )

    # Check if session already exists
    existing = db.query(OnlineHearing).filter(OnlineHearing.hearing_id == session_in.hearing_id).first()
    if existing:
        return build_online_hearing_response(existing)

    case_num = hearing.case.case_number if hearing.case else f"CASE_{hearing.case_id}"
    provider = settings.VIRTUAL_COURT_PROVIDER.strip().lower()
    if provider == "google_meet":
        if session_in.meeting_passcode:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="Google Meet manages meeting admission; an application passcode cannot be set.",
            )
        meeting_link, provider_space_name = GoogleMeetService.create_space()
        meeting_passcode = None
    elif provider == "jitsi":
        _, meeting_link, generated_passcode = VirtualCourtService.generate_room_details(
            hearing.hearing_id, case_num
        )
        meeting_passcode = session_in.meeting_passcode or generated_passcode
        provider_space_name = None
    else:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="VIRTUAL_COURT_PROVIDER must be either 'jitsi' or 'google_meet'.",
        )

    # Update hearing mode to Online/Hybrid
    if hearing.hearing_type == "Physical":
        hearing.hearing_type = "Online"

    online_hearing = OnlineHearing(
        hearing_id=hearing.hearing_id,
        meeting_link=meeting_link,
        meeting_passcode=meeting_passcode,
        meeting_provider=provider,
        provider_space_name=provider_space_name,
        is_recorded=False
    )
    db.add(online_hearing)
    db.commit()
    db.refresh(online_hearing)

    AuditService.log(
        db=db,
        action="VIRTUAL_HEARING_CREATED",
        entity_type="OnlineHearing",
        entity_id=str(online_hearing.online_hearing_id),
        user_id=current_user.user_id,
        details=f"Virtual hearing session generated for Hearing #{hearing.hearing_id}",
        ip_address=client_ip
    )

    return build_online_hearing_response(online_hearing)


@router.post("/sessions/{online_hearing_id}/join", response_model=JoinHearingResponse, summary="Join Virtual Court Hearing")
def join_virtual_hearing(
    online_hearing_id: int,
    request: Request = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """
    Role-gated join access. Verifies authorization and tracks attendance (FR-4.6.3 VirtualHearing.Join & VirtualHearing.Attendance.Track).
    """
    client_ip = request.client.host if (request and request.client) else None

    oh = db.query(OnlineHearing).filter(OnlineHearing.online_hearing_id == online_hearing_id).first()
    if not oh:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Virtual hearing session not found")

    # Verify authorization
    is_authorized = VirtualCourtService.verify_participant_access(db, current_user, oh.hearing)
    if not is_authorized:
        AuditService.log(
            db=db,
            action="UNAUTHORIZED_JOIN_ATTEMPT",
            entity_type="OnlineHearing",
            entity_id=str(online_hearing_id),
            user_id=current_user.user_id,
            details=f"User {current_user.username} ({current_user.role.value}) denied access to Virtual Hearing #{online_hearing_id}",
            ip_address=client_ip
        )
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access Denied: You are not authorized to attend this court proceeding (BR-5.9)."
        )

    # Date restriction: Cannot join proceeding before the scheduled date
    today = date.today()
    if oh.hearing and oh.hearing.hearing_date > today:
        formatted_date = oh.hearing.hearing_date.strftime("%d-%b-%Y")
        formatted_time = oh.hearing.hearing_time.strftime("%I:%M %p") if oh.hearing.hearing_time else ""
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Virtual courtroom is not open yet. This hearing is scheduled for {formatted_date} at {formatted_time}. Participants may only join on the scheduled date."
        )

    if oh.hearing and oh.hearing.hearing_status in ("Completed", "Concluded", "Cancelled", "Adjourned"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Cannot join proceeding. This hearing status is '{oh.hearing.hearing_status}'."
        )

    meeting_url = urlparse(oh.meeting_link)
    if oh.meeting_provider == "google_meet":
        valid_meeting_url = (
            meeting_url.scheme == "https"
            and meeting_url.hostname == "meet.google.com"
            and not meeting_url.query
            and not meeting_url.fragment
        )
    else:
        provider_url = urlparse(settings.VIRTUAL_COURT_BASE_URL)
        provider_path = provider_url.path.rstrip("/")
        valid_meeting_url = (
            provider_url.scheme == "https"
            and meeting_url.scheme == "https"
            and meeting_url.netloc.lower() == provider_url.netloc.lower()
            and meeting_url.path.startswith(f"{provider_path}/")
            and not meeting_url.query
            and not meeting_url.fragment
        )
    if not valid_meeting_url:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="The conference link does not match the configured HTTPS provider. Contact court administration."
        )

    # Log attendance
    VirtualCourtService.record_attendance_join(db, oh.online_hearing_id, current_user, client_ip)

    room_name = oh.provider_space_name or oh.meeting_link.rstrip("/").split("/")[-1]

    AuditService.log(
        db=db,
        action="VIRTUAL_HEARING_JOINED",
        entity_type="OnlineHearing",
        entity_id=str(online_hearing_id),
        user_id=current_user.user_id,
        details=f"{current_user.name} ({current_user.role.value}) joined session",
        ip_address=client_ip
    )

    return JoinHearingResponse(
        online_hearing_id=oh.online_hearing_id,
        meeting_url=oh.meeting_link,
        room_name=room_name,
        participant_name=current_user.name,
        role=current_user.role.value,
        meeting_provider=oh.meeting_provider,
    )


@router.post("/sessions/{online_hearing_id}/leave", summary="Leave Virtual Court Hearing")
def leave_virtual_hearing(
    online_hearing_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """
    Records departure timestamp in attendance tracking log.
    """
    get_authorized_online_hearing(online_hearing_id, db, current_user)
    VirtualCourtService.record_attendance_leave(db, online_hearing_id, current_user.user_id)
    return {"message": f"Recorded departure for {current_user.name}."}


@router.post("/sessions/{online_hearing_id}/start", response_model=OnlineHearingResponse, summary="Start Online Hearing")
def start_online_hearing(
    online_hearing_id: int,
    request: Request = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(UserRole.JUDGE, UserRole.COURT_CLERK, UserRole.ADMINISTRATOR))
):
    """
    Judge commences proceeding. Sets start time and updates hearing status to 'In Progress'.
    """
    client_ip = request.client.host if (request and request.client) else None
    oh = db.query(OnlineHearing).filter(OnlineHearing.online_hearing_id == online_hearing_id).first()
    if not oh:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Virtual hearing session not found")
    if current_user.role == UserRole.JUDGE and (not oh.hearing or oh.hearing.judge_id != current_user.user_id):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Only the assigned judge may start this hearing")

    if oh.hearing and oh.hearing.hearing_date > date.today():
        formatted_date = oh.hearing.hearing_date.strftime("%d-%b-%Y")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Cannot commence hearing before the scheduled date ({formatted_date})."
        )

    oh.start_time = datetime.utcnow()
    if oh.hearing:
        oh.hearing.hearing_status = "In Progress"

    db.commit()
    db.refresh(oh)

    AuditService.log(
        db=db,
        action="HEARING_STARTED",
        entity_type="OnlineHearing",
        entity_id=str(online_hearing_id),
        user_id=current_user.user_id,
        details=f"Hearing #{oh.hearing_id} commenced by {current_user.name}",
        ip_address=client_ip
    )

    return build_online_hearing_response(oh)


@router.post("/sessions/{online_hearing_id}/recording", response_model=OnlineHearingResponse, summary="Recording capture (unavailable)")
def toggle_recording(
    online_hearing_id: int,
    enable: bool = Query(...),
    request: Request = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(UserRole.JUDGE, UserRole.ADMINISTRATOR))
):
    """Reject recording requests until the configured provider supports capture."""
    raise HTTPException(
        status_code=status.HTTP_501_NOT_IMPLEMENTED,
        detail="Recording capture is not configured for the current video conference provider."
    )


@router.post("/sessions/{online_hearing_id}/end", response_model=OnlineHearingResponse, summary="Conclude Hearing and save session record")
def end_online_hearing(
    online_hearing_id: int,
    notes: Optional[str] = Query(None, description="Bench notes or summary"),
    request: Request = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(UserRole.JUDGE, UserRole.COURT_CLERK, UserRole.ADMINISTRATOR))
):
    """Conclude the proceeding and save session metadata and optional bench notes."""
    client_ip = request.client.host if (request and request.client) else None
    oh = db.query(OnlineHearing).filter(OnlineHearing.online_hearing_id == online_hearing_id).first()
    if not oh:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Virtual hearing session not found")
    if current_user.role == UserRole.JUDGE and (not oh.hearing or oh.hearing.judge_id != current_user.user_id):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Only the assigned judge may conclude this hearing")

    oh.end_time = datetime.utcnow()
    if not oh.start_time:
        oh.start_time = oh.end_time

    if oh.hearing:
        oh.hearing.hearing_status = "Completed"

    # Save session metadata and notes; no live audio transcription provider is configured.
    transcript = VirtualCourtService.generate_session_record(db, oh, notes=notes)

    db.commit()
    db.refresh(oh)

    AuditService.log(
        db=db,
        action="HEARING_CONCLUDED",
        entity_type="OnlineHearing",
        entity_id=str(online_hearing_id),
        user_id=current_user.user_id,
        details=f"Hearing #{oh.hearing_id} concluded and session record #{transcript.transcript_id} saved",
        ip_address=client_ip
    )

    return build_online_hearing_response(oh)


@router.get("/sessions/{online_hearing_id}/attendees", response_model=List[AttendanceRecordResponse], summary="Get Attendance Roster")
def get_attendees(
    online_hearing_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """
    Retrieves complete attendance roster for the proceeding (FR-4.6.3 VirtualHearing.Attendance.Track).
    """
    get_authorized_online_hearing(online_hearing_id, db, current_user)
    attendees = db.query(HearingAttendance).filter(
        HearingAttendance.online_hearing_id == online_hearing_id
    ).order_by(HearingAttendance.joined_at.asc()).all()
    return [AttendanceRecordResponse.model_validate(a) for a in attendees]


@router.get("/sessions/{online_hearing_id}/transcript", response_model=TranscriptResponse, summary="Get Hearing Transcript")
def get_transcript(
    online_hearing_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """Retrieve the participant-restricted hearing session record and any bench notes."""
    get_authorized_online_hearing(online_hearing_id, db, current_user)
    transcript = db.query(Transcript).filter(Transcript.online_hearing_id == online_hearing_id).first()
    if not transcript:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Transcript not available for this hearing")

    words = len(transcript.transcript_text.split())
    return TranscriptResponse(
        transcript_id=transcript.transcript_id,
        online_hearing_id=transcript.online_hearing_id,
        generated_date=transcript.generated_date,
        transcript_text=transcript.transcript_text,
        word_count=words
    )


@router.get("/sessions/{online_hearing_id}/transcript/pdf", summary="Download Transcript PDF")
def download_transcript_pdf(
    online_hearing_id: int,
    request: Request = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """
    Exports and downloads authenticated transcript PDF (Transcript.download()).
    """
    client_ip = request.client.host if (request and request.client) else None
    oh = get_authorized_online_hearing(online_hearing_id, db, current_user)
    if not oh.transcript:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Transcript not found")

    pdf_path = VirtualCourtService.generate_transcript_pdf(oh.transcript, oh)

    AuditService.log(
        db=db,
        action="TRANSCRIPT_DOWNLOADED",
        entity_type="Transcript",
        entity_id=str(oh.transcript.transcript_id),
        user_id=current_user.user_id,
        details=f"Transcript #{oh.transcript.transcript_id} downloaded by {current_user.username}",
        ip_address=client_ip
    )

    return FileResponse(
        path=pdf_path,
        filename=os.path.basename(pdf_path),
        media_type="application/pdf"
    )
