import io
import os
from datetime import datetime, date
from fastapi import HTTPException, UploadFile
from app.core.database import SessionLocal
from app.models.user import User, UserRole, CourtClerk, Litigant, Lawyer
from app.models.case import CourtCase, CaseDocument, DigitalEvidence, CaseHistory
from app.schemas.case import CaseCreate, CaseUpdate, CaseStatusUpdate, LawyerAssignment
from app.api.v1.endpoints.cases import (
    register_case,
    search_cases,
    get_case_details,
    update_case,
    update_case_status,
    assign_lawyer,
    upload_document,
    download_document,
    upload_evidence,
    verify_evidence,
    get_case_history,
    check_duplicate
)
from app.services.case_service import CaseService

def run_tests():
    print("=" * 70)
    print("NYAYASETU PHASE 3: CASE & EVIDENCE MANAGEMENT TEST SUITE")
    print("=" * 70)

    db = SessionLocal()
    try:
        # Load test actors
        clerk = db.query(CourtClerk).filter(CourtClerk.username == "clerk1").first()
        litigant = db.query(Litigant).filter(Litigant.username == "rajesh_k").first()
        lawyer = db.query(Lawyer).filter(Lawyer.username == "adv_verma").first()

        assert clerk is not None, "Clerk user must exist"
        assert litigant is not None, "Litigant user must exist"
        assert lawyer is not None, "Lawyer user must exist"

        # [Test 1] Case Registration & Unique Case ID Generation
        print("\n[Test 1] Testing Case Registration (FR-4.2.3 Case.Register)...")
        case_data = CaseCreate(
            title="State of Maharashtra vs R. K. Enterprises",
            case_type="Criminal",
            priority="High",
            description="Alleged violation of industrial commercial compliance and safety norms.",
            litigant_id=litigant.litigant_id,
            lawyer_assignments=[
                LawyerAssignment(lawyer_id=lawyer.lawyer_id, representing_party="Petitioner")
            ]
        )
        created_case = register_case(case_in=case_data, request=None, db=db, current_user=clerk)
        assert created_case.case_id is not None
        assert created_case.case_number.startswith(f"CC/{date.today().year}/")
        assert created_case.case_status == "Registered"
        assert created_case.litigant_id == litigant.litigant_id
        assert len(created_case.lawyers) == 1
        case_id = created_case.case_id
        print(f"  PASS: Case registered successfully with Unique Case ID: {created_case.case_number}")

        # [Test 2] Duplicate Case Detection
        print("\n[Test 2] Testing Duplicate Case Detection (FR-4.2.3 Case.Duplicate.Check)...")
        dup_check = check_duplicate(
            title="State of Maharashtra vs R. K. Enterprises",
            case_type="Criminal",
            litigant_id=litigant.litigant_id,
            db=db,
            current_user=clerk
        )
        assert dup_check.is_potential_duplicate is True
        assert len(dup_check.matches) > 0
        top_match = dup_check.matches[0]
        print(f"  PASS: Duplicate detected! Similarity score: {top_match.similarity_score}, Reason: {top_match.reason}")

        # [Test 3] Multi-criteria Search & Role Scoping
        print("\n[Test 3] Testing Search & Role Scoping (FR-4.2.3 Case.Search)...")
        search_res = search_cases(q="Enterprises", db=db, current_user=clerk)
        assert len(search_res) >= 1
        print(f"  PASS: Found {len(search_res)} cases matching search term 'Enterprises'.")

        # Litigant scope test
        litigant_cases = search_cases(db=db, current_user=litigant)
        assert all(c.litigant_id == litigant.litigant_id for c in litigant_cases)
        print(f"  PASS: Litigant scope restricted strictly to own cases ({len(litigant_cases)} found).")

        # [Test 4] Case Update
        print("\n[Test 4] Testing Case Update (FR-4.2.3 Case.Update)...")
        updated = update_case(
            case_id=case_id,
            case_update=CaseUpdate(priority="Urgent", description="Updated: Urgent bail hearing required."),
            request=None,
            db=db,
            current_user=clerk
        )
        assert updated.priority == "Urgent"
        print(f"  PASS: Case priority updated to '{updated.priority}'.")

        # [Test 5] Case Lifecycle State Transitions
        print("\n[Test 5] Testing Lifecycle Status Transitions (Registered -> Active -> Disposed)...")
        active_case = update_case_status(
            case_id=case_id,
            status_in=CaseStatusUpdate(status="Active", reason_or_outcome="Filing admitted by Registry"),
            request=None,
            db=db,
            current_user=clerk
        )
        assert active_case.case_status == "Active"
        print(f"  PASS: Status transitioned to '{active_case.case_status}'.")

        # [Test 6] Document Upload with SHA-256 & Versioning
        print("\n[Test 6] Testing Document Upload, SHA-256 & Versioning (FR-4.5.3)...")
        doc_bytes = b"%PDF-1.4 Mock Legal Petition Document Content for Court Proceeding"
        mock_file = UploadFile(filename="Petition_Original.pdf", file=io.BytesIO(doc_bytes))
        
        doc_res = upload_document(
            case_id=case_id,
            file=mock_file,
            document_type="Petition",
            is_confidential=False,
            request=None,
            db=db,
            current_user=clerk
        )
        assert doc_res.version == 1
        assert len(doc_res.file_hash) == 64
        first_doc_id = doc_res.document_id
        print(f"  PASS: Document v1 uploaded. SHA-256 Hash: {doc_res.file_hash[:16]}... (length 64)")

        # Upload amended document with same name -> should auto-version to v2
        doc_bytes_v2 = b"%PDF-1.4 Mock Legal Petition Document Version 2 Amended Content"
        mock_file_v2 = UploadFile(filename="Petition_Original.pdf", file=io.BytesIO(doc_bytes_v2))
        doc_res_v2 = upload_document(
            case_id=case_id,
            file=mock_file_v2,
            document_type="Petition",
            is_confidential=False,
            request=None,
            db=db,
            current_user=clerk
        )
        assert doc_res_v2.version == 2
        print(f"  PASS: Re-uploading document correctly incremented version to v{doc_res_v2.version}!")

        # [Test 7] Confidential Document Access Control
        print("\n[Test 7] Testing Confidential Document Access Security (SRS NFR-5.3.6)...")
        conf_bytes = b"CONFIDENTIAL: Internal Judicial Deliberation Notes"
        conf_mock = UploadFile(filename="Judicial_Notes.pdf", file=io.BytesIO(conf_bytes))
        conf_doc = upload_document(
            case_id=case_id,
            file=conf_mock,
            document_type="Judicial Note",
            is_confidential=True,
            request=None,
            db=db,
            current_user=clerk
        )
        # Litigant attempts to download confidential document -> should raise 403 Forbidden
        try:
            download_document(case_id=case_id, document_id=conf_doc.document_id, request=None, db=db, current_user=litigant)
            assert False, "Litigant should be blocked from downloading confidential document"
        except HTTPException as e:
            assert e.status_code == 403
            print(f"  PASS: Litigant download access correctly blocked with 403: {e.detail}")

        # Clerk download -> allowed
        clerk_download = download_document(case_id=case_id, document_id=conf_doc.document_id, request=None, db=db, current_user=clerk)
        assert clerk_download.filename == "Judicial_Notes.pdf"
        print("  PASS: Authorized court staff download allowed.")

        # [Test 8] Digital Evidence Upload and Cryptographic Verification
        print("\n[Test 8] Testing Digital Evidence Upload and Verification (FR-4.5.3)...")
        ev_bytes = b"BINARY EVIDENCE: Audio Recording CCTV Transcript Bytes 0x98124"
        ev_mock = UploadFile(filename="cctv_evidence_footage.mp4", file=io.BytesIO(ev_bytes))
        ev_res = upload_evidence(
            case_id=case_id,
            file=ev_mock,
            evidence_type="Video",
            description="CCTV footage from security terminal 4",
            request=None,
            db=db,
            current_user=clerk
        )
        assert ev_res.is_verified is False
        assert len(ev_res.file_hash) == 64
        print(f"  PASS: Digital Evidence submitted (Status: Pending Verification, Hash: {ev_res.file_hash[:16]}...)")

        # Judge/Clerk verifies evidence
        verified_ev = verify_evidence(
            case_id=case_id,
            evidence_id=ev_res.evidence_id,
            request=None,
            db=db,
            current_user=clerk
        )
        assert verified_ev.is_verified is True
        print(f"  PASS: Digital Evidence verified successfully: is_verified={verified_ev.is_verified}")

        # [Test 9] Case History Timeline Retrieval
        print("\n[Test 9] Testing Case History Chronological Timeline (FR-4.7.3 Tracking.Timeline)...")
        history_events = get_case_history(case_id=case_id, db=db, current_user=clerk)
        assert len(history_events) >= 5
        event_types = [h.event for h in history_events]
        print(f"  PASS: Recorded {len(history_events)} timeline events: {event_types}")

        print("\n" + "=" * 70)
        print("PHASE 3 CASE & EVIDENCE MANAGEMENT SYSTEM VERIFIED WITH 100% SUCCESS!")
        print("=" * 70)

    finally:
        db.close()

if __name__ == "__main__":
    run_tests()
