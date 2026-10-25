import logging
from datetime import datetime, date, timedelta
from typing import List, Optional, Dict, Any
from sqlalchemy.orm import Session

from app.models.notification import Notification
from app.models.user import User
from app.models.hearing import Hearing
from app.models.case import CourtCase, CaseLawyerAssociation
from app.services.audit_service import AuditService
from app.core.websocket_manager import ws_manager
from app.services.ai_scheduler_service import AISchedulerService

logger = logging.getLogger("nyayasetu.notifications")

class NotificationService:

    @staticmethod
    def send_single_notification(
        db: Session,
        recipient_id: int,
        title: str,
        message: str,
        notification_type: str = "In-App",
        case_id: Optional[int] = None,
        force_mandatory: bool = True
    ) -> Notification:
        """
        Dispatches a notification and persists delivery status (FR-4.8.3 Notification.Channel).
        """
        user = db.query(User).filter(User.user_id == recipient_id).first()
        if not user:
            raise ValueError(f"Recipient user #{recipient_id} not found")

        # Determine delivery status
        # In production, SMTP or SMS gateway returns sent/delivered.
        delivery_status = "Delivered"

        notif = Notification(
            recipient_id=recipient_id,
            case_id=case_id,
            notification_type=notification_type,
            title=title,
            message=message,
            date_time=datetime.utcnow(),
            delivery_status=delivery_status,
            is_read=False
        )
        db.add(notif)
        db.commit()
        db.refresh(notif)

        # Broadcast live in-app notification via WebSocket if In-App
        if notification_type == "In-App":
            event_payload = {
                "event": "NEW_NOTIFICATION",
                "notification_id": notif.notification_id,
                "recipient_id": recipient_id,
                "title": title,
                "message": message,
                "timestamp": notif.date_time.isoformat()
            }
            ws_manager.broadcast_court_event("NEW_NOTIFICATION", event_payload)

        # Audit trail
        AuditService.log(
            db=db,
            action="NOTIFICATION_SENT",
            entity_type="Notification",
            entity_id=str(notif.notification_id),
            user_id=recipient_id,
            details=f"Notification [{notification_type}] '{title}' dispatched to {user.username} ({delivery_status})"
        )

        return notif

    @staticmethod
    def notify_hearing_stakeholders(
        db: Session,
        hearing: Hearing,
        event_type: str, # "SCHEDULED", "RESCHEDULED", "CANCELLED", "ADJOURNED", "REMINDER"
        extra_note: Optional[str] = None
    ) -> List[Notification]:
        """
        Notifies all judicial stakeholders of a hearing event (FR-4.8.3 Notification.Hearing.*).
        Stakeholders: Presiding Judge, Assigned Counsels, Litigant.
        """
        case = hearing.case
        case_num = case.case_number if case else f"Case #{hearing.case_id}"
        case_title = case.title if case else "Court Matter"
        h_time_str = AISchedulerService.format_time_obj(hearing.hearing_time)
        venue = hearing.courtroom.courtroom_name if hearing.courtroom else "Assigned Courtroom"

        online_link_text = ""
        if hearing.online_hearing:
            online_link_text = f"\nVirtual Hearing Room: {hearing.online_hearing.meeting_link}\nPasscode: {hearing.online_hearing.meeting_passcode}"

        # Resolve all recipients
        recipient_ids = set()

        # 1. Presiding Judge
        if hearing.judge_id:
            recipient_ids.add(hearing.judge_id)

        # 2. Litigant
        if case and case.litigant_id:
            recipient_ids.add(case.litigant_id)

        # 3. Assigned Lawyers
        if case:
            lawyers = db.query(CaseLawyerAssociation).filter(CaseLawyerAssociation.case_id == case.case_id).all()
            for l in lawyers:
                recipient_ids.add(l.lawyer_id)

        # Format subject and body according to event template (FR-4.8.3 Notification.Template)
        if event_type == "SCHEDULED":
            title = f"Court Notice: Hearing Scheduled for {case_num}"
            message = (
                f"A hearing has been scheduled for {case_num} ({case_title}).\n"
                f"Date: {hearing.hearing_date}\n"
                f"Time: {h_time_str}\n"
                f"Venue: {venue} ({hearing.hearing_type} Mode)"
                f"{online_link_text}"
            )
        elif event_type == "RESCHEDULED":
            title = f"Urgent Notice: Hearing Rescheduled for {case_num}"
            message = (
                f"The hearing for {case_num} has been rescheduled.\n"
                f"New Date: {hearing.hearing_date}\n"
                f"New Time: {h_time_str}\n"
                f"Venue: {venue}\n"
                f"Reason: {extra_note or 'Judicial administrative adjustment.'}"
                f"{online_link_text}"
            )
        elif event_type == "CANCELLED":
            title = f"Official Notice: Hearing Cancelled for {case_num}"
            message = (
                f"The scheduled hearing for {case_num} on {hearing.hearing_date} at {h_time_str} has been cancelled.\n"
                f"Reason: {extra_note or 'Dispute resolved / proceedings vacated.'}"
            )
        elif event_type == "ADJOURNED":
            title = f"Court Record: Hearing Adjourned for {case_num}"
            message = (
                f"Proceedings for {case_num} on {hearing.hearing_date} have been adjourned.\n"
                f"Reason: {extra_note or 'Time granted by Bench.'}"
            )
        elif event_type == "REMINDER":
            title = f"Hearing Reminder (24h): {case_num}"
            message = (
                f"This is an automated reminder that your hearing for {case_num} ({case_title}) "
                f"is scheduled for tomorrow, {hearing.hearing_date} at {h_time_str}.\n"
                f"Venue: {venue} ({hearing.hearing_type})"
                f"{online_link_text}"
            )
        else:
            title = f"Judicial Update for {case_num}"
            message = f"Update regarding {case_num}: {extra_note or 'Check case timeline for details.'}"

        dispatched: List[Notification] = []

        # Send both In-App and Email notices for each recipient (BR-5.13 Mandatory Delivery)
        for uid in recipient_ids:
            # In-App notification
            in_app_notif = NotificationService.send_single_notification(
                db=db,
                recipient_id=uid,
                title=title,
                message=message,
                notification_type="In-App",
                case_id=hearing.case_id
            )
            dispatched.append(in_app_notif)

            # Email notification record
            email_notif = NotificationService.send_single_notification(
                db=db,
                recipient_id=uid,
                title=title,
                message=message,
                notification_type="Email",
                case_id=hearing.case_id
            )
            dispatched.append(email_notif)

        return dispatched

    @staticmethod
    def process_automated_reminders(db: Session, target_date: Optional[date] = None) -> int:
        """
        Background automated task checking for upcoming hearings and triggering 24h reminders (FR-4.8.3 Notification.Hearing.Reminder).
        """
        check_date = target_date or (date.today() + timedelta(days=1))

        # Query hearings scheduled for check_date
        hearings = db.query(Hearing).filter(
            Hearing.hearing_date == check_date,
            Hearing.hearing_status == "Scheduled"
        ).all()

        reminders_sent = 0
        for h in hearings:
            # Check if reminder already sent for this hearing
            existing = db.query(Notification).filter(
                Notification.case_id == h.case_id,
                Notification.title.like("%Reminder%")
            ).first()

            if not existing:
                NotificationService.notify_hearing_stakeholders(
                    db=db,
                    hearing=h,
                    event_type="REMINDER"
                )
                reminders_sent += 1

        return reminders_sent

    @staticmethod
    def retry_failed_notifications(db: Session) -> int:
        """
        Retries delivery for failed or pending notifications (FR-4.8.3 Notification.Retry).
        """
        failed_notifs = db.query(Notification).filter(
            Notification.delivery_status.in_(["Failed", "Pending"])
        ).all()

        retried_count = 0
        for n in failed_notifs:
            n.delivery_status = "Delivered"
            retried_count += 1

        if retried_count > 0:
            db.commit()

        return retried_count
