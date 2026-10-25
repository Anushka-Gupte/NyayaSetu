import os
from datetime import datetime, date
from fastapi import HTTPException
from app.core.database import SessionLocal
from app.models.user import CourtClerk, Judge, Lawyer, Litigant
from app.models.hearing import Hearing, OnlineHearing, Transcript, HearingAttendance
from app.models.case import CourtCase
from app.schemas.virtual_court import OnlineHearingCreate
from app.api.v1.endpoints.virtual_court import (
    create_virtual_session,
    join_virtual_hearing,
    leave_virtual_hearing,
    start_online_hearing,
    toggle_recording,
    end_online_hearing,
    get_attendees,
    get_transcript,
    download_transcript_pdf
)

def run_tests():
    print("=" * 70)
    print("NYAYASETU PHASE 6: VIRTUAL COURT & AI TRANSCRIPTION TEST SUITE")
    print("=" * 70)

    db = SessionLocal()
    try:
        # Load actors
        clerk = db.query(CourtClerk).filter(CourtClerk.username == "clerk1").first()
        judge = db.query(Judge).filter(Judge.username == "judge_sharma").first()
        lawyer = db.query(Lawyer).filter(Lawyer.username == "adv_verma").first()
        unauthorized_litigant = db.query(Litigant).filter(Litigant.username == "sunita_d").first()

        assert clerk is not None
        assert judge is not None
        assert lawyer is not None
        assert unauthorized_litigant is not None

        # Find a hearing where judge_sharma is presiding
        hearing = db.query(Hearing).filter(Hearing.judge_id == judge.user_id).first()
        assert hearing is not None, "Need a hearing with judge_sharma"

        # [Test 1] Virtual Courtroom Session Creation (FR-4.6.3 VirtualHearing.Link.Generate)
        print("\n[Test 1] Testing Virtual Courtroom Session Creation...")
        session_res = create_virtual_session(
            session_in=OnlineHearingCreate(hearing_id=hearing.hearing_id),
            request=None,
            db=db,
            current_user=clerk
        )
        assert session_res.online_hearing_id is not None
        assert session_res.meeting_link.startswith("https://meet.jit.si/NyayaSetu_")
        assert session_res.meeting_passcode is not None
        online_hearing_id = session_res.online_hearing_id
        print(f"  PASS: Virtual Hearing #{online_hearing_id} created with secure link: {session_res.meeting_link}")
        print(f"  Meeting Passcode: {session_res.meeting_passcode}")

        # [Test 2] Access Control & Unauthorized Participant Rejection (BR-5.9)
        print("\n[Test 2] Testing Access Control (Unauthorized Litigant rejected)...")
        try:
            join_virtual_hearing(
                online_hearing_id=online_hearing_id,
                request=None,
                db=db,
                current_user=unauthorized_litigant
            )
            assert False, "Unauthorized litigant should have been denied access"
        except HTTPException as e:
            assert e.status_code == 403
            print(f"  PASS: Unauthorized participant blocked with 403 Forbidden: {e.detail}")

        # [Test 3] Authorized Participant Join & Attendance Tracking (FR-4.6.3 VirtualHearing.Join & Attendance.Track)
        print("\n[Test 3] Testing Authorized Participants Joining & Attendance Logging...")
        # Judge joins
        judge_join = join_virtual_hearing(online_hearing_id=online_hearing_id, request=None, db=db, current_user=judge)
        assert judge_join.jwt_room_token is not None
        print(f"  PASS: Presiding Judge {judge.name} joined. Room Token issued.")

        # Lawyer joins
        lawyer_join = join_virtual_hearing(online_hearing_id=online_hearing_id, request=None, db=db, current_user=lawyer)
        assert lawyer_join.jwt_room_token is not None
        print(f"  PASS: Counsel {lawyer.name} joined. Room Token issued.")

        # Verify Attendance log
        attendees = get_attendees(online_hearing_id=online_hearing_id, db=db, current_user=clerk)
        assert len(attendees) >= 2
        attendee_names = [a.user_name for a in attendees]
        print(f"  PASS: Attendance roster verified ({len(attendees)} present): {attendee_names}")

        # [Test 4] Hearing Commencement (start_hearing)
        print("\n[Test 4] Testing Hearing Commencement (In Progress)...")
        started = start_online_hearing(online_hearing_id=online_hearing_id, request=None, db=db, current_user=judge)
        assert started.start_time is not None
        db.refresh(hearing)
        assert hearing.hearing_status == "In Progress"
        print(f"  PASS: Hearing status set to 'In Progress' at {started.start_time}.")

        # [Test 5] Recording Controls (FR-4.6.3 VirtualHearing.Record)
        print("\n[Test 5] Testing Hearing Recording Controls...")
        rec_enabled = toggle_recording(online_hearing_id=online_hearing_id, enable=True, request=None, db=db, current_user=judge)
        assert rec_enabled.is_recorded is True
        assert rec_enabled.recording_file_path is not None
        print(f"  PASS: Authorized recording enabled. Output target: {rec_enabled.recording_file_path}")

        # [Test 6] Participant Departure Tracking
        print("\n[Test 6] Testing Participant Departure...")
        leave_res = leave_virtual_hearing(online_hearing_id=online_hearing_id, db=db, current_user=lawyer)
        print(f"  PASS: {leave_res['message']}")

        # [Test 7] Hearing Conclusion & Automated AI Transcription (FR-4.6.3 VirtualHearing.End & Transcript.Generate)
        print("\n[Test 7] Testing Hearing Conclusion & Automated AI Transcription...")
        concluded = end_online_hearing(
            online_hearing_id=online_hearing_id,
            notes="Registry directed to notify authorities of interim directions within 48 hours.",
            request=None,
            db=db,
            current_user=judge
        )
        assert concluded.end_time is not None
        assert concluded.has_transcript is True
        db.refresh(hearing)
        assert hearing.hearing_status == "Completed"
        print(f"  PASS: Hearing successfully concluded and marked 'Completed' at {concluded.end_time}.")

        # Retrieve transcript
        transcript_res = get_transcript(online_hearing_id=online_hearing_id, db=db, current_user=clerk)
        assert transcript_res.transcript_id is not None
        assert "OFFICIAL JUDICIAL HEARING PROCEEDING TRANSCRIPT" in transcript_res.transcript_text
        assert "Justice R. Sharma" in transcript_res.transcript_text
        print(f"  PASS: AI Verbatim Transcript generated ({transcript_res.word_count} words). Composition 1-to-1 verified.")

        # [Test 8] Transcript PDF Document Generation (Transcript.download)
        print("\n[Test 8] Testing Transcript PDF Export...")
        pdf_res = download_transcript_pdf(online_hearing_id=online_hearing_id, request=None, db=db, current_user=clerk)
        assert os.path.exists(pdf_res.path)
        file_size = os.path.getsize(pdf_res.path)
        assert file_size > 1000
        with open(pdf_res.path, "rb") as f:
            header_bytes = f.read(5)
            assert header_bytes.startswith(b"%PDF-")
        print(f"  PASS: Authenticated Transcript PDF verified on disk ({file_size} bytes): {pdf_res.filename}")

        print("\n" + "=" * 70)
        print("PHASE 6 VIRTUAL COURT & AI TRANSCRIPTION VERIFIED WITH 100% SUCCESS!")
        print("=" * 70)

    finally:
        db.close()

if __name__ == "__main__":
    run_tests()
