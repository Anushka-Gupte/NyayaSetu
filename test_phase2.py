from datetime import datetime
from fastapi import HTTPException
from app.core.database import SessionLocal
from app.models.user import User, UserRole, CourtClerk
from app.models.audit import AuditLog
from app.schemas.auth import LoginRequest, UserCreate, UserUpdateStatus
from app.api.v1.endpoints.auth import login, get_me, logout
from app.api.v1.endpoints.users import create_user, list_users, update_user_status
from app.api.v1.endpoints.dashboard import get_dashboard_overview
from app.api.v1.endpoints.audit import list_audit_logs
from app.api.deps import require_roles

def run_tests():
    print("=" * 70)
    print("NYAYASETU PHASE 2: RBAC & AUTHENTICATION TEST SUITE")
    print("=" * 70)

    db = SessionLocal()
    try:
        # [Test 1] Administrator Login & JWT Generation
        print("\n[Test 1] Testing Administrator Login...")
        login_res = login(LoginRequest(username_or_email="admin", password="Password@123"), request=None, db=db)
        assert login_res.role == UserRole.ADMINISTRATOR
        assert login_res.access_token is not None
        print(f"  PASS: Admin authenticated successfully. Token type: {login_res.token_type}")

        # [Test 2] Invalid Credentials Handling & Audit Logging
        print("\n[Test 2] Testing Invalid Credentials & Security Audit...")
        try:
            login(LoginRequest(username_or_email="admin", password="WrongPassword!"), request=None, db=db)
            assert False, "Should have raised 401 HTTPException"
        except HTTPException as e:
            assert e.status_code == 401
            print(f"  PASS: Correctly raised 401: {e.detail}")

        failed_audit = db.query(AuditLog).filter(AuditLog.action == "LOGIN_FAILED").first()
        assert failed_audit is not None
        print(f"  PASS: Security Audit recorded failed attempt for entity_type={failed_audit.entity_type}")

        # [Test 3] Profile Retrieval (/auth/me)
        print("\n[Test 3] Testing User Profile Retrieval...")
        admin_user = db.query(User).filter(User.username == "admin").first()
        profile = get_me(current_user=admin_user)
        assert profile.username == "admin"
        assert profile.admin_role == "SUPER_ADMIN"
        print(f"  PASS: Profile retrieved for {profile.name} (Role: {profile.role.value}, Admin Role: {profile.admin_role})")

        # [Test 4] Multi-Role User Authentication
        print("\n[Test 4] Testing Authentication Across All 5 Roles...")
        role_accounts = [
            ("clerk1", UserRole.COURT_CLERK, "employee_id"),
            ("judge_sharma", UserRole.JUDGE, "specialization"),
            ("adv_verma", UserRole.LAWYER, "bar_registration_no"),
            ("rajesh_k", UserRole.LITIGANT, "address")
        ]
        user_objects = {}
        for username, expected_role, expected_field in role_accounts:
            res = login(LoginRequest(username_or_email=username, password="Password@123"), request=None, db=db)
            assert res.role == expected_role
            user_obj = db.query(User).filter(User.username == username).first()
            user_objects[expected_role] = user_obj
            prof = get_me(current_user=user_obj)
            val = getattr(prof, expected_field)
            assert val is not None
            print(f"  PASS: {expected_role.value} ({username}) verified with {expected_field}='{val}'")

        # [Test 5] Role-Based Access Control (RBAC) Guard
        print("\n[Test 5] Testing RBAC Security Guard (Non-Admin blocked from Admin endpoints)...")
        litigant_user = user_objects[UserRole.LITIGANT]
        admin_guard = require_roles(UserRole.ADMINISTRATOR)
        try:
            admin_guard(current_user=litigant_user)
            assert False, "Litigant should have been blocked by RBAC guard"
        except HTTPException as e:
            assert e.status_code == 403
            print(f"  PASS: Blocked unauthorized role with 403 Forbidden: {e.detail}")

        # [Test 6] Admin User Onboarding
        print("\n[Test 6] Testing Admin User Onboarding (FR-4.1.3 Authentication.Role.Assign)...")
        new_username = "test_clerk_p2"
        existing = db.query(User).filter(User.username == new_username).first()
        if not existing:
            new_clerk = create_user(
                user_in=UserCreate(
                    name="Pooja Sharma (Clerk)",
                    email="pooja.clerk@court.gov.in",
                    mobile_no="9876543299",
                    username=new_username,
                    password="Password@123",
                    role=UserRole.COURT_CLERK,
                    employee_id="EMP-CLK-999"
                ),
                request=None,
                db=db,
                current_admin=admin_user
            )
            assert new_clerk.username == new_username
            assert new_clerk.employee_id == "EMP-CLK-999"
            print(f"  PASS: Admin created new user: {new_clerk.name} ({new_clerk.role.value})")
        else:
            print(f"  PASS: User {new_username} verified in database.")

        # [Test 7] Role-Tailored Dashboard Metrics (SRS Section 3.1)
        print("\n[Test 7] Testing Dynamic Dashboards for Each Role...")
        # Admin dashboard
        d_admin = get_dashboard_overview(db=db, current_user=admin_user)
        assert "total_users" in d_admin["metrics"]
        print(f"  PASS: Admin Dashboard -> total_users={d_admin['metrics']['total_users']}, courtrooms={d_admin['metrics']['total_courtrooms']}")

        # Judge dashboard
        judge_user = user_objects[UserRole.JUDGE]
        d_judge = get_dashboard_overview(db=db, current_user=judge_user)
        assert "assigned_cases_count" in d_judge["metrics"]
        print(f"  PASS: Judge Dashboard -> assigned_cases={d_judge['metrics']['assigned_cases_count']}")

        # Lawyer dashboard
        lawyer_user = user_objects[UserRole.LAWYER]
        d_lawyer = get_dashboard_overview(db=db, current_user=lawyer_user)
        assert "total_assigned_cases" in d_lawyer["metrics"]
        print(f"  PASS: Lawyer Dashboard -> total_assigned_cases={d_lawyer['metrics']['total_assigned_cases']}")

        # Litigant dashboard
        d_litigant = get_dashboard_overview(db=db, current_user=litigant_user)
        assert "my_cases_count" in d_litigant["metrics"]
        print(f"  PASS: Litigant Dashboard -> my_cases_count={d_litigant['metrics']['my_cases_count']}")

        # [Test 8] Audit Trail Listing
        print("\n[Test 8] Testing Audit Log Retrieval (SRS NFR-5.3.7)...")
        logs = list_audit_logs(db=db, current_admin=admin_user)
        assert len(logs) > 0
        print(f"  PASS: Retrieved {len(logs)} audit trail entries. Top actions: {[l.action for l in logs[:3]]}")

        print("\n" + "=" * 70)
        print("PHASE 2 RBAC & AUTHENTICATION SYSTEM VERIFIED WITH 100% SUCCESS!")
        print("=" * 70)

    finally:
        db.close()

if __name__ == "__main__":
    run_tests()
