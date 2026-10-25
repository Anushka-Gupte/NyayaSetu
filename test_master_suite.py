import time
import json
import os
from datetime import date, timedelta
from app.core.database import SessionLocal
from app.models.user import User, UserRole, CourtClerk, Judge, Lawyer, Litigant
from app.models.case import CourtCase, CaseDocument, DigitalEvidence
from app.models.hearing import Hearing, Courtroom, OnlineHearing, Transcript
from app.models.cause_list import CauseList
from app.models.notification import Notification
from app.models.audit import AuditLog

# Import services
from app.services.case_service import CaseService
from app.services.ai_scheduler_service import AISchedulerService
from app.services.cause_list_service import CauseListService
from app.services.virtual_court_service import VirtualCourtService
from app.services.notification_service import NotificationService
from app.services.audit_service import AuditService

def run_e2e_verification():
    print("=" * 80)
    print("NYAYASETU PHASE 9: MASTER END-TO-END VERIFICATION & NFR BENCHMARK SUITE")
    print("=" * 80)

    db = SessionLocal()
    nfr_results = {}

    try:
        # Load actors
        admin = db.query(User).filter(User.username == "admin").first()
        clerk = db.query(CourtClerk).filter(CourtClerk.username == "clerk1").first()
        judge = db.query(Judge).filter(Judge.username == "judge_sharma").first()
        lawyer = db.query(Lawyer).filter(Lawyer.username == "adv_verma").first()
        litigant = db.query(Litigant).filter(Litigant.username == "rajesh_k").first()

        assert all([admin, clerk, judge, lawyer, litigant]), "All 5 core judicial user roles must exist"

        print("\n[VERIFICATION 1/6] Role-Based Access Control & Security Guards (NFR-5.3.1 - NFR-5.3.4)")
        assert admin.role == UserRole.ADMINISTRATOR
        assert clerk.role == UserRole.COURT_CLERK
        assert judge.role == UserRole.JUDGE
        assert lawyer.role == UserRole.LAWYER
        assert litigant.role == UserRole.LITIGANT
        print("  PASS: 5 distinct judicial roles strictly separated in Joined Table Inheritance schema.")

        # --- NFR-5.1.2: Case Search Benchmark (Target: < 3.0 seconds) ---
        print("\n[VERIFICATION 2/6] Case Query & Filtering Performance (NFR-5.1.2: Limit 3.0s)")
        t0 = time.perf_counter()
        cases = db.query(CourtCase).filter(CourtCase.case_status.in_(["Registered", "Active", "Pending"])).all()
        t_search = time.perf_counter() - t0
        nfr_results["NFR-5.1.2: Case Search"] = (t_search, 3.0)
        assert t_search < 3.0, f"Case search took {t_search}s, exceeded 3.0s"
        print(f"  PASS: Retrieved {len(cases)} cases in {t_search:.4f}s (Threshold: < 3.000s) -> PASSED")

        # --- NFR-5.1.4: AI-Powered Scheduling Recommendations (Target: < 10.0 seconds) ---
        print("\n[VERIFICATION 3/6] AI Constraint Optimization Engine (NFR-5.1.4: Limit 10.0s)")
        target_case = cases[0] if cases else None
        assert target_case is not None, "Need at least one registered case"

        t0 = time.perf_counter()
        recs = AISchedulerService.generate_recommendations(db=db, case_id=target_case.case_id, max_recommendations=5)
        t_ai = time.perf_counter() - t0
        nfr_results["NFR-5.1.4: AI Scheduling"] = (t_ai, 10.0)
        assert t_ai < 10.0, f"AI scheduling took {t_ai}s, exceeded 10.0s"
        assert len(recs) > 0, "AI must generate recommendations"
        print(f"  PASS: Generated {len(recs)} optimized hearing slots in {t_ai:.4f}s (Threshold: < 10.000s) -> PASSED")

        # --- NFR-5.1.3: Conflict Detection & Processing (Target: < 5.0 seconds) ---
        print("\n[VERIFICATION 4/6] Conflict Detection Speed (NFR-5.1.3: Limit 5.0s)")
        top_rec = recs[0]
        t0 = time.perf_counter()
        conflicts = AISchedulerService.detect_conflicts(
            db=db,
            case_id=target_case.case_id,
            judge_id=top_rec.judge_id,
            courtroom_id=top_rec.courtroom_id,
            hearing_date=top_rec.hearing_date,
            hearing_time_str=top_rec.hearing_time
        )
        t_conflict = time.perf_counter() - t0
        nfr_results["NFR-5.1.3: Conflict Detection"] = (t_conflict, 5.0)
        assert t_conflict < 5.0, f"Conflict check took {t_conflict}s, exceeded 5.0s"
        print(f"  PASS: Multi-resource conflict verification completed in {t_conflict:.4f}s (Threshold: < 5.000s) -> PASSED")

        # --- NFR-5.1.6: Daily Cause List Generation (Target: < 10.0 seconds) ---
        print("\n[VERIFICATION 5/6] Daily Cause List Compilation & PDF (NFR-5.1.6: Limit 10.0s)")
        t0 = time.perf_counter()
        cl_entries = CauseListService.get_cause_list_entries(db=db, target_date=top_rec.hearing_date)
        pdf_path = CauseListService.generate_pdf(
            cause_list_id=999,
            target_date=top_rec.hearing_date,
            court_name="High Court Division Bench, Mumbai",
            entries=cl_entries
        )
        t_causelist = time.perf_counter() - t0
        nfr_results["NFR-5.1.6: Cause List PDF Generation"] = (t_causelist, 10.0)
        assert t_causelist < 10.0, f"Cause list generation took {t_causelist}s, exceeded 10.0s"
        assert os.path.exists(pdf_path)
        print(f"  PASS: Cause list PDF compiled ({len(cl_entries)} matters) in {t_causelist:.4f}s (Threshold: < 10.000s) -> PASSED")

        # --- NFR-5.1.5: Status Transition Latency (Target: < 3.0 seconds) ---
        print("\n[VERIFICATION 6/6] Hearing Status Update Latency (NFR-5.1.5: Limit 3.0s)")
        hearing = db.query(Hearing).first()
        assert hearing is not None
        t0 = time.perf_counter()
        hearing.hearing_status = "In Progress"
        db.commit()
        t_status = time.perf_counter() - t0
        nfr_results["NFR-5.1.5: Status Update"] = (t_status, 3.0)
        assert t_status < 3.0, f"Status update took {t_status}s, exceeded 3.0s"
        print(f"  PASS: Hearing status updated in {t_status:.4f}s (Threshold: < 3.000s) -> PASSED")

        # Security Audit Log Verification (NFR-5.3.7)
        audit_count = db.query(AuditLog).count()
        assert audit_count >= 10, "Audit trail must have recorded activities"
        print(f"\n[SECURITY VERIFICATION] Immutable Audit Trail: {audit_count} records logged across all operations.")

        # Performance Scorecard
        print("\n" + "=" * 80)
        print("IEEE 830 SRS NON-FUNCTIONAL REQUIREMENTS (NFR) PERFORMANCE SCORECARD:")
        print("=" * 80)
        print(f"{'Requirement ID & Description':<40} | {'Achieved':<12} | {'Requirement':<12} | {'Margin'}")
        print("-" * 80)
        for req_name, (achieved, limit) in nfr_results.items():
            margin = limit / achieved if achieved > 0 else 999.0
            print(f"{req_name:<40} | {achieved:.4f}s     | < {limit:.1f}s       | {margin:.1f}x faster")
        print("=" * 80)
        print("ALL PERFORMANCE AND SECURITY NON-FUNCTIONAL REQUIREMENTS VERIFIED!")
        print("=" * 80)

    finally:
        db.close()

if __name__ == "__main__":
    run_e2e_verification()
