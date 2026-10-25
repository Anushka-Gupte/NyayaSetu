from typing import List, Optional
from datetime import datetime, date
from fastapi import APIRouter, Depends, HTTPException, status, Query, Request
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.models.user import User, UserRole
from app.models.notification import Notification
from app.schemas.notification import (
    NotificationCreate,
    NotificationResponse,
    NotificationStats
)
from app.api.deps import get_current_active_user, require_roles
from app.services.notification_service import NotificationService
from app.services.audit_service import AuditService

router = APIRouter()

def build_notification_response(n: Notification) -> NotificationResponse:
    rec_name = n.recipient.name if n.recipient else f"User #{n.recipient_id}"
    return NotificationResponse(
        notification_id=n.notification_id,
        recipient_id=n.recipient_id,
        recipient_name=rec_name,
        case_id=n.case_id,
        notification_type=n.notification_type,
        title=n.title,
        message=n.message,
        date_time=n.date_time,
        delivery_status=n.delivery_status,
        is_read=n.is_read
    )

@router.get("", response_model=List[NotificationResponse], summary="Get Current User Notifications")
def get_user_notifications(
    unread_only: bool = False,
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """
    Returns notification history for the authenticated user (FR-4.8.3 Notification.History).
    """
    query = db.query(Notification).filter(Notification.recipient_id == current_user.user_id)
    if unread_only:
        query = query.filter(Notification.is_read == False)

    limit_val = limit if isinstance(limit, int) else 50
    offset_val = offset if isinstance(offset, int) else 0

    notifs = query.order_by(Notification.date_time.desc()).offset(offset_val).limit(limit_val).all()
    return [build_notification_response(n) for n in notifs]


@router.put("/{notification_id}/read", response_model=NotificationResponse, summary="Mark Notification as Read")
def mark_notification_read(
    notification_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """
    Marks a single notification as read.
    """
    notif = db.query(Notification).filter(
        Notification.notification_id == notification_id,
        Notification.recipient_id == current_user.user_id
    ).first()
    if not notif:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Notification not found")

    notif.is_read = True
    db.commit()
    db.refresh(notif)
    return build_notification_response(notif)


@router.put("/read-all", summary="Mark All Notifications as Read")
def mark_all_read(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """
    Clears unread badge count by marking all user's notifications as read.
    """
    db.query(Notification).filter(
        Notification.recipient_id == current_user.user_id,
        Notification.is_read == False
    ).update({"is_read": True})
    db.commit()
    return {"message": "All notifications marked as read."}


@router.post("/send", response_model=NotificationResponse, status_code=status.HTTP_201_CREATED, summary="Send Manual Court Notification")
def send_manual_notification(
    notif_in: NotificationCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(UserRole.COURT_CLERK, UserRole.ADMINISTRATOR))
):
    """
    Court staff manually dispatches an official alert to a specific judicial participant.
    """
    notif = NotificationService.send_single_notification(
        db=db,
        recipient_id=notif_in.recipient_id,
        title=notif_in.title,
        message=notif_in.message,
        notification_type=notif_in.notification_type,
        case_id=notif_in.case_id
    )
    return build_notification_response(notif)


@router.post("/trigger-reminders", summary="Trigger Automated 24h Hearing Reminders")
def trigger_reminders(
    target_date: Optional[date] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(UserRole.COURT_CLERK, UserRole.ADMINISTRATOR))
):
    """
    Invokes automated background reminder scan for scheduled hearings (FR-4.8.3 Notification.Hearing.Reminder).
    """
    reminders_sent = NotificationService.process_automated_reminders(db, target_date=target_date)
    return {
        "status": "success",
        "reminders_dispatched": reminders_sent,
        "message": f"Dispatched automated reminders for {reminders_sent} scheduled hearings."
    }


@router.post("/retry-failed", summary="Retry Failed Notification Deliveries")
def retry_failed(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(UserRole.ADMINISTRATOR))
):
    """
    Retries undelivered or failed email/SMS alerts according to retry policy (FR-4.8.3 Notification.Retry).
    """
    retried_count = NotificationService.retry_failed_notifications(db)
    return {
        "status": "success",
        "retried_count": retried_count,
        "message": f"Successfully reprocessed {retried_count} notifications."
    }


@router.get("/stats", response_model=NotificationStats, summary="Notification System Delivery Statistics")
def get_notification_stats(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(UserRole.ADMINISTRATOR, UserRole.COURT_CLERK))
):
    """
    Returns operational notification metrics for judicial administrators.
    """
    total = db.query(Notification).count()
    delivered = db.query(Notification).filter(Notification.delivery_status == "Delivered").count()
    pending = db.query(Notification).filter(Notification.delivery_status == "Pending").count()
    failed = db.query(Notification).filter(Notification.delivery_status == "Failed").count()
    sent = delivered + pending
    unread = db.query(Notification).filter(Notification.is_read == False).count()

    return NotificationStats(
        total_notifications=total,
        sent_count=sent,
        delivered_count=delivered,
        failed_count=failed,
        pending_count=pending,
        unread_count=unread
    )
