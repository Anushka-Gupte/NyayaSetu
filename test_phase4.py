import time
from datetime import date, timedelta
from fastapi import HTTPException
from app.core.database import SessionLocal
from app.models.user import CourtClerk, Judge
from app.models.case import CourtCase
from app.models.hearing import Hearing, Courtroom
from app.schemas.hearing import (
    HearingRecommendationRequest,
    HearingScheduleCreate,
    HearingRescheduleRequest,
    HearingCancelRequest,
    HearingAdjournRequest,
    HearingCompleteRequest,
    ConflictCheckRequest
)
from app.api.v1.endpoints.hearings import (
    get_ai_recommendations,
    check_conflicts,
    schedule_hearing,
    reschedule_hearing,
    cancel_hearing,
    adjourn_hearing,
    complete_hearing,
    list_hearings
)

def run_tests():
    print("=" * 70)
    print("NYAYASETU PHASE 4: AI SCHEDULING & RESOURCE ALLOCATION TEST SUITE")
    print("=" * 70)

    db = SessionLocal()
    try:
        # Load test actors
        clerk = db.query(CourtClerk).filter(CourtClerk.username == "clerk1").first()
        judge = db.query(Judge).filter(Judge.username == "judge_sharma").first()
        courtroom = db.query(Courtroom).first()
        case = db.query(CourtCase).first()

        assert clerk is not None
        assert judge is not None
        assert courtroom is not None
        assert case is not None

        # [Test 1] AI-Powered Recommendation Engine & Performance Benchmark
        print("\n[Test 1] Testing AI Scheduling Recommendations (FR-4.3.3 & NFR-5.1.4)...")
        start_time = time.time()
        rec_res = get_ai_recommendations(
            req=HearingRecommendationRequest(case_id=case.case_id),
            db=db,
            current_user=clerk
        )
        elapsed_sec = time.time() - start_time
        assert len(rec_res.recommendations) > 0, "Expected at least 1 recommendation"
        top_rec = rec_res.recommendations[0]
        assert top_rec.confidence_score >= 0.70
        print(f"  PASS: Generated {len(rec_res.recommendations)} AI recommendations in {elapsed_sec:.4f}s (NFR limit: 10s).")
        print(f"  Top Slot: {top_rec.hearing_date} at {top_rec.hearing_time} before {top_rec.judge_name} in {top_rec.courtroom_name}")
        print(f"  Confidence: {top_rec.confidence_score*100:.1f}%, Reasons: {top_rec.reasons}")

        # [Test 2] Hearing Scheduling (FR-4.3.3 Scheduling.Create)
        print("\n[Test 2] Scheduling Hearing using AI Recommendation...")
        sched_in = HearingScheduleCreate(
            case_id=case.case_id,
            judge_id=top_rec.judge_id,
            courtroom_id=top_rec.courtroom_id,
            hearing_date=top_rec.hearing_date,
            hearing_time=top_rec.hearing_time,
            hearing_type="Physical",
            is_ai_recommended=True
        )
        created_hearing = schedule_hearing(schedule_in=sched_in, request=None, db=db, current_user=clerk)
        assert created_hearing.hearing_id is not None
        assert created_hearing.hearing_status == "Scheduled"
        hearing_id = created_hearing.hearing_id
        print(f"  PASS: Hearing #{hearing_id} successfully scheduled on {created_hearing.hearing_date} at {created_hearing.hearing_time}")

        # [Test 3] Conflict Detection (FR-4.3.3 Scheduling.Conflict.Detect)
        print("\n[Test 3] Testing Automated Conflict Detection...")
        conflict_probe = check_conflicts(
            check=ConflictCheckRequest(
                case_id=case.case_id,
                judge_id=top_rec.judge_id,
                courtroom_id=top_rec.courtroom_id,
                hearing_date=top_rec.hearing_date,
                hearing_time=top_rec.hearing_time
            ),
            db=db,
            current_user=clerk
        )
        assert conflict_probe.has_conflict is True
        assert len(conflict_probe.conflicts) >= 1
        print(f"  PASS: Conflict detected! Details: {conflict_probe.conflicts}")
        assert len(conflict_probe.suggested_alternatives) > 0
        print(f"  PASS: Automatically suggested {len(conflict_probe.suggested_alternatives)} alternative slots.")

        # [Test 4] Double-Booking Prevention (BR-5.3)
        print("\n[Test 4] Testing Double-Booking Prevention Guard (BR-5.3)...")
        try:
            schedule_hearing(schedule_in=sched_in, request=None, db=db, current_user=clerk)
            assert False, "Should have thrown 409 Conflict on double-booking"
        except HTTPException as e:
            assert e.status_code == 409
            print(f"  PASS: Successfully blocked double-booking with 409 Conflict: {e.detail}")

        # [Test 5] Rescheduling Hearing (FR-4.3.3 Scheduling.Reschedule)
        print("\n[Test 5] Testing Hearing Rescheduling...")
        # Find next alternative slot
        alt_slot = conflict_probe.suggested_alternatives[0]
        rescheduled = reschedule_hearing(
            hearing_id=hearing_id,
            reschedule_in=HearingRescheduleRequest(
                new_date=alt_slot.hearing_date,
                new_time=alt_slot.hearing_time,
                new_courtroom_id=alt_slot.courtroom_id,
                new_judge_id=alt_slot.judge_id,
                reason="Courtroom maintenance scheduled on original date."
            ),
            request=None,
            db=db,
            current_user=clerk
        )
        assert rescheduled.hearing_date == alt_slot.hearing_date
        assert rescheduled.hearing_time == alt_slot.hearing_time
        print(f"  PASS: Hearing #{hearing_id} successfully rescheduled to {rescheduled.hearing_date} at {rescheduled.hearing_time}")

        # [Test 6] Adjournment Workflow (FR-4.7.3 Tracking.Hearing.Adjourn)
        print("\n[Test 6] Testing Judicial Adjournment Workflow...")
        adjourned = adjourn_hearing(
            hearing_id=hearing_id,
            adjourn_in=HearingAdjournRequest(
                reason="Counsel for Respondent requested 7 days to file counter-affidavit.",
                next_hearing_date=date.today() + timedelta(days=14)
            ),
            request=None,
            db=db,
            current_user=clerk
        )
        assert adjourned.hearing_status == "Adjourned"
        assert "counter-affidavit" in adjourned.adjournment_reason
        print(f"  PASS: Hearing #{hearing_id} marked as 'Adjourned'. Reason recorded.")

        # [Test 7] Hearing Completion Workflow (FR-4.7.3 Tracking.Hearing.Complete)
        print("\n[Test 7] Testing Hearing Completion Workflow...")
        completed = complete_hearing(
            hearing_id=hearing_id,
            complete_in=HearingCompleteRequest(
                outcome="Interim relief granted. Registry directed to issue notice to concerned authorities."
            ),
            request=None,
            db=db,
            current_user=clerk
        )
        assert completed.hearing_status == "Completed"
        assert "Interim relief" in completed.outcome
        print(f"  PASS: Hearing #{hearing_id} marked as 'Completed' with recorded judicial order.")

        # [Test 8] Cancellation Workflow (FR-4.3.3 Scheduling.Cancel)
        print("\n[Test 8] Testing Hearing Cancellation & Resource Release...")
        # Create temporary hearing on a weekday to cancel
        candidate_cancel_date = date.today() + timedelta(days=20)
        while candidate_cancel_date.weekday() in (5, 6):
            candidate_cancel_date += timedelta(days=1)

        temp_sched = schedule_hearing(
            schedule_in=HearingScheduleCreate(
                case_id=case.case_id,
                judge_id=judge.judge_id,
                courtroom_id=courtroom.courtroom_id,
                hearing_date=candidate_cancel_date,
                hearing_time="14:00",
                hearing_type="Physical"
            ),
            request=None,
            db=db,
            current_user=clerk
        )
        cancelled = cancel_hearing(
            hearing_id=temp_sched.hearing_id,
            cancel_in=HearingCancelRequest(reason="Settlement reached between parties outside court."),
            request=None,
            db=db,
            current_user=clerk
        )
        assert cancelled.hearing_status == "Cancelled"
        print(f"  PASS: Hearing #{temp_sched.hearing_id} cancelled and resources released.")

        print("\n" + "=" * 70)
        print("PHASE 4 AI SCHEDULING & RESOURCE ALLOCATION VERIFIED WITH 100% SUCCESS!")
        print("=" * 70)

    finally:
        db.close()

if __name__ == "__main__":
    run_tests()
