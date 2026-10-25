from typing import List, Optional, Dict, Any
from datetime import datetime, date
from fastapi import APIRouter, Depends, HTTPException, status, Query, Request, WebSocket, WebSocketDisconnect
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.models.user import User, UserRole
from app.models.hearing import Hearing, Courtroom
from app.models.case import CourtCase, CaseHistory
from app.schemas.tracking import (
    HearingPostponeRequest,
    LiveHearingInfo,
    CourtroomDisplayBoard,
    CaseTimelineMilestone,
    CaseTimelineResponse
)
from app.api.deps import get_current_active_user, require_roles
from app.services.audit_service import AuditService
from app.services.ai_scheduler_service import AISchedulerService
from app.core.websocket_manager import ws_manager

router = APIRouter()

def build_live_info(h: Hearing) -> LiveHearingInfo:
    c = h.case
    j = h.judge
    return LiveHearingInfo(
        hearing_id=h.hearing_id,
        case_id=h.case_id,
        case_number=c.case_number if c else f"Case #{h.case_id}",
        case_title=c.title if c else "Matter",
        judge_name=j.name if j else "Presiding Judge",
        hearing_time=AISchedulerService.format_time_obj(h.hearing_time),
        hearing_status=h.hearing_status,
        hearing_type=h.hearing_type
    )

def compile_courtroom_board(db: Session, cr: Courtroom, target_date: date) -> CourtroomDisplayBoard:
    # Find currently in-progress hearing
    current_h = db.query(Hearing).filter(
        Hearing.courtroom_id == cr.courtroom_id,
        Hearing.hearing_date == target_date,
        Hearing.hearing_status == "In Progress"
    ).first()

    # Find next scheduled hearing
    next_h = db.query(Hearing).filter(
        Hearing.courtroom_id == cr.courtroom_id,
        Hearing.hearing_date == target_date,
        Hearing.hearing_status == "Scheduled"
    ).order_by(Hearing.hearing_time.asc()).first()

    today_hearings = db.query(Hearing).filter(
        Hearing.courtroom_id == cr.courtroom_id,
        Hearing.hearing_date == target_date,
        Hearing.hearing_status != "Cancelled"
    ).count()

    bench_status = "IN_SESSION" if current_h else ("AVAILABLE" if next_h else "RECESS")

    return CourtroomDisplayBoard(
        courtroom_id=cr.courtroom_id,
        courtroom_name=cr.courtroom_name,
        location=cr.location,
        bench_status=bench_status,
        current_matter=build_live_info(current_h) if current_h else None,
        next_matter=build_live_info(next_h) if next_h else None,
        today_total_matters=today_hearings
    )


@router.get("/courtrooms/display-board", response_model=List[CourtroomDisplayBoard], summary="Courtroom Live Digital Display Boards")
def get_live_display_boards(
    target_date: Optional[date] = None,
    db: Session = Depends(get_db)
):
    """
    Public judicial display board showing currently proceeding matters across all courtrooms (SRS Section 4.7).
    """
    query_date = target_date or date.today()
    courtrooms = db.query(Courtroom).order_by(Courtroom.courtroom_id.asc()).all()
    return [compile_courtroom_board(db, cr, query_date) for cr in courtrooms]


@router.get("/courtrooms/{courtroom_id}/display", response_model=CourtroomDisplayBoard, summary="Single Courtroom Display")
def get_courtroom_display(
    courtroom_id: int,
    target_date: Optional[date] = None,
    db: Session = Depends(get_db)
):
    """
    Returns live display board for a specific courtroom entrance screen.
    """
    cr = db.query(Courtroom).filter(Courtroom.courtroom_id == courtroom_id).first()
    if not cr:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Courtroom not found")
    query_date = target_date or date.today()
    return compile_courtroom_board(db, cr, query_date)


@router.put("/hearings/{hearing_id}/start", summary="Commence Hearing Proceeding (In Progress)")
def commence_hearing(
    hearing_id: int,
    request: Request = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(UserRole.JUDGE, UserRole.COURT_CLERK, UserRole.ADMINISTRATOR))
):
    """
    Marks hearing as 'In Progress' and broadcasts live update across WebSockets (FR-4.7.3 Tracking.Hearing.Start).
    """
    client_ip = request.client.host if (request and request.client) else None
    hearing = db.query(Hearing).filter(Hearing.hearing_id == hearing_id).first()
    if not hearing:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Hearing not found")

    hearing.hearing_status = "In Progress"

    history_entry = CaseHistory(
        case_id=hearing.case_id,
        event="HEARING_IN_PROGRESS",
        date_time=datetime.utcnow(),
        description=f"Hearing #{hearing.hearing_id} commenced in {hearing.courtroom.courtroom_name if hearing.courtroom else 'courtroom'}.",
        user_id=current_user.user_id
    )
    db.add(history_entry)
    db.commit()
    db.refresh(hearing)

    # Real-Time WebSocket Event Broadcast (SRS Section 3.4)
    event_payload = {
        "event": "NOW_HEARING",
        "hearing_id": hearing.hearing_id,
        "case_id": hearing.case_id,
        "case_number": hearing.case.case_number if hearing.case else "",
        "courtroom_id": hearing.courtroom_id,
        "courtroom_name": hearing.courtroom.courtroom_name if hearing.courtroom else "",
        "judge_name": hearing.judge.name if hearing.judge else "",
        "status": "In Progress",
        "timestamp": datetime.utcnow().isoformat()
    }
    ws_manager.broadcast_court_event("NOW_HEARING", event_payload)

    AuditService.log(
        db=db,
        action="HEARING_COMMENCED",
        entity_type="Hearing",
        entity_id=str(hearing.hearing_id),
        user_id=current_user.user_id,
        details=f"Hearing #{hearing.hearing_id} set to 'In Progress'",
        ip_address=client_ip
    )

    return {"message": f"Hearing #{hearing.hearing_id} commenced. Live display boards updated."}


@router.put("/hearings/{hearing_id}/postpone", summary="Postpone Hearing")
def postpone_hearing(
    hearing_id: int,
    postpone_in: HearingPostponeRequest,
    request: Request = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(UserRole.COURT_CLERK, UserRole.ADMINISTRATOR))
):
    """
    Postpones a scheduled hearing and records reason (FR-4.7.3 Tracking.Hearing.Postpone).
    """
    client_ip = request.client.host if (request and request.client) else None
    hearing = db.query(Hearing).filter(Hearing.hearing_id == hearing_id).first()
    if not hearing:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Hearing not found")

    hearing.hearing_status = "Postponed"
    hearing.adjournment_reason = f"Postponed: {postpone_in.reason}"

    desc = f"Hearing #{hearing.hearing_id} postponed. Reason: {postpone_in.reason}."
    if postpone_in.new_hearing_date:
        desc += f" Next date proposed: {postpone_in.new_hearing_date}."

    history_entry = CaseHistory(
        case_id=hearing.case_id,
        event="HEARING_POSTPONED",
        date_time=datetime.utcnow(),
        description=desc,
        user_id=current_user.user_id
    )
    db.add(history_entry)
    db.commit()
    db.refresh(hearing)

    # Real-Time WebSocket Broadcast
    event_payload = {
        "event": "HEARING_STATUS_CHANGED",
        "hearing_id": hearing.hearing_id,
        "case_id": hearing.case_id,
        "courtroom_id": hearing.courtroom_id,
        "status": "Postponed",
        "reason": postpone_in.reason,
        "timestamp": datetime.utcnow().isoformat()
    }
    ws_manager.broadcast_court_event("HEARING_STATUS_CHANGED", event_payload)

    AuditService.log(
        db=db,
        action="HEARING_POSTPONED",
        entity_type="Hearing",
        entity_id=str(hearing.hearing_id),
        user_id=current_user.user_id,
        details=f"Hearing #{hearing.hearing_id} postponed: {postpone_in.reason}",
        ip_address=client_ip
    )

    return {"message": f"Hearing #{hearing.hearing_id} postponed."}


@router.get("/cases/{case_id}/timeline", response_model=CaseTimelineResponse, summary="Get Full Visual Case Timeline")
def get_case_timeline(
    case_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """
    Returns full chronological visual timeline of milestones from registration to disposal (FR-4.7.3 Tracking.Timeline).
    """
    case = db.query(CourtCase).filter(CourtCase.case_id == case_id).first()
    if not case:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Case not found")

    # Scoping for Litigant
    if current_user.role == UserRole.LITIGANT and case.litigant_id != current_user.user_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access denied")

    history_records = sorted(case.history, key=lambda x: x.date_time, reverse=True)

    milestones: List[CaseTimelineMilestone] = []
    for h in history_records:
        actor = db.query(User).filter(User.user_id == h.user_id).first() if h.user_id else None
        milestones.append(CaseTimelineMilestone(
            history_id=h.history_id,
            event=h.event,
            date_time=h.date_time,
            description=h.description,
            user_id=h.user_id,
            actor_name=actor.name if actor else "System"
        ))

    return CaseTimelineResponse(
        case_id=case.case_id,
        case_number=case.case_number,
        case_title=case.title,
        case_status=case.case_status,
        priority=case.priority,
        filing_date=case.filing_date,
        total_events=len(milestones),
        timeline=milestones
    )


# ==============================================================================
# WebSocket Live Gateway (SRS Section 3.4 & 4.7)
# ==============================================================================

@router.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    """
    Real-time WebSocket endpoint. Clients receive live hearing progress and board updates.
    Can send: {"action": "subscribe", "topic": "courtroom:1"} or {"action": "subscribe", "topic": "case:1"}
    """
    await ws_manager.connect(websocket)
    try:
        while True:
            data_text = await websocket.receive_text()
            try:
                msg = json.loads(data_text)
                action = msg.get("action")
                topic = msg.get("topic")
                if action == "subscribe" and topic:
                    ws_manager.subscribe(websocket, topic)
                    await websocket.send_text(json.dumps({"status": "subscribed", "topic": topic}))
                elif action == "unsubscribe" and topic:
                    ws_manager.unsubscribe(websocket, topic)
                    await websocket.send_text(json.dumps({"status": "unsubscribed", "topic": topic}))
                elif action == "ping":
                    await websocket.send_text(json.dumps({"status": "pong"}))
            except Exception:
                pass
    except WebSocketDisconnect:
        ws_manager.disconnect(websocket)
