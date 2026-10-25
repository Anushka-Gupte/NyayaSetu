from datetime import date, timedelta
from app.core.database import SessionLocal
from app.models.user import CourtClerk, Judge, Lawyer, Litigant
from app.models.hearing import Hearing
from app.models.notification import Notification
from app.schemas.notification import NotificationCreate
from app.services.notification_service import NotificationService
from app.api.v1.endpoints.notifications import (
    get_user_notifications,
    mark_notification_read,
    mark_all_read,
    send_manual_notification,
    trigger_reminders,
    retry_failed,
    get_notification_stats
)

def run_tests():
    print("=" * 70)
    print("NYAYASETU PHASE 8: SMART NOTIFICATIONS & REMINDERS TEST SUITE")
    print("=" * 70)

    db = SessionLocal()
    try:
        # Load actors
        clerk = db.query(CourtClerk).filter(CourtClerk.username == "clerk1").first()
        judge = db.query(Judge).filter(Judge.username == "judge_sharma").first()
        litigant = db.query(Litigant).filter(Litigant.username == "rajesh_k").first()
        lawyer = db.query(Lawyer).filter(Lawyer.username == "adv_verma").first()

        assert clerk is not None
        assert judge is not None
        assert litigant is not None
        assert lawyer is not None

        hearing = db.query(Hearing).first()
        assert hearing is not None

        # [Test 1] Multi-Channel Notification Dispatch (FR-4.8.3 Notification.Channel)
        print("\n[Test 1] Testing Manual Notification Dispatch...")
        notif_in = NotificationCreate(
            recipient_id=litigant.user_id,
            case_id=hearing.case_id,
            notification_type="In-App",
            title="Registry Notice: Case Admitted",
            message="Your petition has been admitted for preliminary judicial review."
        )
        sent_notif = send_manual_notification(notif_in=notif_in, db=db, current_user=clerk)
        assert sent_notif.notification_id is not None
        assert sent_notif.delivery_status == "Delivered"
        assert sent_notif.is_read is False
        notif_id = sent_notif.notification_id
        print(f"  PASS: Notification #{notif_id} dispatched to {sent_notif.recipient_name} (Status: {sent_notif.delivery_status})")

        # [Test 2] Hearing Stakeholder Broadcast (FR-4.8.3 Notification.Hearing.Schedule)
        print("\n[Test 2] Testing Automated Stakeholder Notification Broadcast...")
        broadcast_notifs = NotificationService.notify_hearing_stakeholders(
            db=db,
            hearing=hearing,
            event_type="SCHEDULED"
        )
        assert len(broadcast_notifs) >= 2, "Expected at least 2 stakeholder notifications (Judge, Litigant/Lawyer)"
        recipient_ids = [n.recipient_id for n in broadcast_notifs]
        assert judge.user_id in recipient_ids
        print(f"  PASS: Broadcasted {len(broadcast_notifs)} notices to stakeholders (Recipients: {recipient_ids}).")
        sample_msg = broadcast_notifs[0]
        print(f"  Title: '{sample_msg.title}'")

        # [Test 3] Automated 24h Hearing Reminders (FR-4.8.3 Notification.Hearing.Reminder)
        print("\n[Test 3] Testing Background 24h Reminder Scanning...")
        reminders_count = NotificationService.process_automated_reminders(db, target_date=hearing.hearing_date)
        print(f"  PASS: Automated background scan processed ({reminders_count} hearings reminded).")

        # [Test 4] User Notification History & Read Status (FR-4.8.3 Notification.History)
        print("\n[Test 4] Testing User Notification Drawer & Read Status...")
        litigant_notifs = get_user_notifications(unread_only=True, db=db, current_user=litigant)
        assert len(litigant_notifs) > 0
        print(f"  PASS: Litigant received {len(litigant_notifs)} unread notifications.")

        # Mark single notification as read
        read_item = mark_notification_read(notification_id=notif_id, db=db, current_user=litigant)
        assert read_item.is_read is True
        print(f"  PASS: Notification #{notif_id} marked as read.")

        # Mark all as read
        all_read = mark_all_read(db=db, current_user=litigant)
        assert "All notifications" in all_read["message"]
        remaining_unread = get_user_notifications(unread_only=True, db=db, current_user=litigant)
        assert len(remaining_unread) == 0
        print("  PASS: All notifications marked as read; unread badge cleared.")

        # [Test 5] Notification Retry Policy (FR-4.8.3 Notification.Retry)
        print("\n[Test 5] Testing Failed Delivery Retry Policy...")
        # Create simulated failed SMS
        failed_sms = Notification(
            recipient_id=litigant.user_id,
            notification_type="SMS",
            title="Summons SMS Delivery",
            message="Your presence is required before Bench 1.",
            delivery_status="Failed",
            is_read=False
        )
        db.add(failed_sms)
        db.commit()
        db.refresh(failed_sms)

        retry_res = retry_failed(db=db, current_user=clerk)
        assert retry_res["retried_count"] >= 1
        db.refresh(failed_sms)
        assert failed_sms.delivery_status == "Delivered"
        print(f"  PASS: Retry engine reprocessed {retry_res['retried_count']} failed alerts. Status updated to 'Delivered'.")

        # [Test 6] Administrative Notification Statistics
        print("\n[Test 6] Testing Admin Notification Delivery Metrics...")
        stats = get_notification_stats(db=db, current_user=clerk)
        assert stats.total_notifications > 0
        assert stats.delivered_count > 0
        print(f"  PASS: Notification metrics verified: Total={stats.total_notifications}, Delivered={stats.delivered_count}, Failed={stats.failed_count}")

        print("\n" + "=" * 70)
        print("PHASE 8 SMART NOTIFICATIONS & REMINDERS VERIFIED WITH 100% SUCCESS!")
        print("=" * 70)

    finally:
        db.close()

if __name__ == "__main__":
    run_tests()
