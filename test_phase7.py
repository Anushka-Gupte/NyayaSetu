from datetime import date
from fastapi import HTTPException
from app.core.database import SessionLocal
from app.models.user import CourtClerk, Judge
from app.models.hearing import Hearing, Courtroom
from app.models.case import CourtCase
from app.schemas.tracking import HearingPostponeRequest
from app.api.v1.endpoints.tracking import (
    get_live_display_boards,
    get_courtroom_display,
    commence_hearing,
    postpone_hearing,
    get_case_timeline
)
from app.core.websocket_manager import ws_manager

def run_tests():
    print("=" * 70)
    print("NYAYASETU PHASE 7: REAL-TIME TRACKING & WEBSOCKET GATEWAY TEST SUITE")
    print("=" * 70)

    db = SessionLocal()
    try:
        # Load actors
        clerk = db.query(CourtClerk).filter(CourtClerk.username == "clerk1").first()
        judge = db.query(Judge).filter(Judge.username == "judge_sharma").first()
        hearing = db.query(Hearing).filter(Hearing.judge_id == judge.user_id).first()
        assert hearing is not None
        case_id = hearing.case_id
        courtroom_id = hearing.courtroom_id
        target_date = hearing.hearing_date

        # [Test 1] Public Digital Display Boards across Courtrooms (SRS Section 4.7)
        print("\n[Test 1] Testing Courtroom Digital Display Boards...")
        boards = get_live_display_boards(target_date=target_date, db=db)
        assert len(boards) >= 4, "Expected at least 4 courtrooms"
        print(f"  PASS: Retrieved display boards for {len(boards)} courtrooms.")
        for b in boards:
            print(f"  [{b.courtroom_name}] Status: {b.bench_status} | Today's Matters: {b.today_total_matters}")

        # [Test 2] Hearing Commencement & Live Board Update (FR-4.7.3 Tracking.Hearing.Start)
        print("\n[Test 2] Commencing Hearing Proceeding (In Progress)...")
        # Ensure hearing is Scheduled
        hearing.hearing_status = "Scheduled"
        db.commit()

        start_res = commence_hearing(hearing_id=hearing.hearing_id, request=None, db=db, current_user=judge)
        assert "commenced" in start_res["message"]
        db.refresh(hearing)
        assert hearing.hearing_status == "In Progress"
        print(f"  PASS: Hearing #{hearing.hearing_id} marked as 'In Progress'.")

        # Verify single courtroom display board reflects current matter
        cr_board = get_courtroom_display(courtroom_id=courtroom_id, target_date=target_date, db=db)
        assert cr_board.bench_status == "IN_SESSION"
        assert cr_board.current_matter is not None
        assert cr_board.current_matter.hearing_id == hearing.hearing_id
        print(f"  PASS: Display board outside Courtroom #{courtroom_id} updated:")
        print(f"  NOW HEARING: {cr_board.current_matter.case_number} - {cr_board.current_matter.case_title} before {cr_board.current_matter.judge_name}")

        # [Test 3] Hearing Postponement Workflow (FR-4.7.3 Tracking.Hearing.Postpone)
        print("\n[Test 3] Testing Hearing Postponement Workflow...")
        postpone_res = postpone_hearing(
            hearing_id=hearing.hearing_id,
            postpone_in=HearingPostponeRequest(
                reason="Adverse weather advisory; proceedings deferred.",
                new_hearing_date=date.today()
            ),
            request=None,
            db=db,
            current_user=clerk
        )
        assert "postponed" in postpone_res["message"]
        db.refresh(hearing)
        assert hearing.hearing_status == "Postponed"
        assert "Postponed: Adverse weather" in hearing.adjournment_reason
        print(f"  PASS: Hearing #{hearing.hearing_id} successfully marked as 'Postponed'.")

        # [Test 4] Full Visual Case Timeline (FR-4.7.3 Tracking.Timeline)
        print("\n[Test 4] Testing Visual Case Timeline Retrieval...")
        timeline_res = get_case_timeline(case_id=case_id, db=db, current_user=clerk)
        assert timeline_res.total_events >= 5
        print(f"  PASS: Case {timeline_res.case_number} timeline contains {timeline_res.total_events} milestones:")
        for m in timeline_res.timeline[:4]:
            print(f"  - [{m.date_time.strftime('%Y-%m-%d %H:%M')}] {m.event} (By {m.actor_name}): {m.description[:65]}...")

        # [Test 5] WebSocket Gateway Event Broadcasts (SRS Section 3.4)
        print("\n[Test 5] Testing WebSocket Gateway Broadcast...")
        test_payload = {
            "courtroom_id": courtroom_id,
            "case_id": case_id,
            "hearing_id": hearing.hearing_id,
            "status": "In Progress"
        }
        ws_manager.broadcast_court_event("NOW_HEARING_TEST", test_payload)
        print("  PASS: WebSocket manager broadcast_court_event executed successfully without errors.")

        print("\n" + "=" * 70)
        print("PHASE 7 REAL-TIME TRACKING & WEBSOCKET GATEWAY VERIFIED WITH 100% SUCCESS!")
        print("=" * 70)

    finally:
        db.close()

if __name__ == "__main__":
    run_tests()
