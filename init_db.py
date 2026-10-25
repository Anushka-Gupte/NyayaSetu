from datetime import datetime, date
from app.core.database import engine, Base, SessionLocal
from app.models import (
    User, Administrator, CourtClerk, Judge, Lawyer, Litigant, UserRole,
    Courtroom, CourtCase, AIScheduler, AuditLog
)
from app.core.security import get_password_hash

def init_database():
    print("=" * 60)
    print("Initializing Database Schema...")
    Base.metadata.create_all(bind=engine)
    print("Schema created successfully!")
    print("=" * 60)

    print("Seeding initial data...")
    with SessionLocal() as session:
        # Check if admin already exists
        existing_admin = session.query(User).filter(User.username == "admin").first()

        if existing_admin:
            print("Database already seeded. Skipping initial data creation.")
            return

        default_hashed_pw = get_password_hash("Password@123")

        # 1. Administrator
        admin = Administrator(
            name="System Administrator",
            email="admin@court.gov.in",
            mobile_no="9876543210",
            username="admin",
            password=default_hashed_pw,
            role=UserRole.ADMINISTRATOR,
            admin_role="SUPER_ADMIN"
        )
        session.add(admin)

        # 2. Court Clerk
        clerk = CourtClerk(
            name="Ramesh Joshi (Clerk)",
            email="clerk1@court.gov.in",
            mobile_no="9876543211",
            username="clerk1",
            password=default_hashed_pw,
            role=UserRole.COURT_CLERK,
            employee_id="EMP-CLK-101"
        )
        session.add(clerk)

        # 3. Judges
        judge1 = Judge(
            name="Hon. Justice R. Sharma",
            email="judge.sharma@court.gov.in",
            mobile_no="9876543212",
            username="judge_sharma",
            password=default_hashed_pw,
            role=UserRole.JUDGE,
            specialization="Criminal Law",
            availability="Available"
        )
        judge2 = Judge(
            name="Hon. Justice P. Patel",
            email="judge.patel@court.gov.in",
            mobile_no="9876543213",
            username="judge_patel",
            password=default_hashed_pw,
            role=UserRole.JUDGE,
            specialization="Civil & Commercial Law",
            availability="Available"
        )
        session.add_all([judge1, judge2])

        # 4. Lawyers
        lawyer1 = Lawyer(
            name="Adv. Vikram Verma",
            email="adv.verma@barcouncil.in",
            mobile_no="9876543214",
            username="adv_verma",
            password=default_hashed_pw,
            role=UserRole.LAWYER,
            bar_registration_no="MAH/4521/2018"
        )
        lawyer2 = Lawyer(
            name="Adv. Meera Rao",
            email="adv.rao@barcouncil.in",
            mobile_no="9876543215",
            username="adv_rao",
            password=default_hashed_pw,
            role=UserRole.LAWYER,
            bar_registration_no="MAH/8912/2020"
        )
        session.add_all([lawyer1, lawyer2])

        # 5. Litigants
        litigant1 = Litigant(
            name="Rajesh Kumar",
            email="rajesh.kumar@gmail.com",
            mobile_no="9876543216",
            username="rajesh_k",
            password=default_hashed_pw,
            role=UserRole.LITIGANT,
            address="12 Lotus Colony, Mumbai 400001"
        )
        litigant2 = Litigant(
            name="Sunita Deshmukh",
            email="sunita.deshmukh@gmail.com",
            mobile_no="9876543217",
            username="sunita_d",
            password=default_hashed_pw,
            role=UserRole.LITIGANT,
            address="45 Dadar West, Mumbai 400028"
        )
        session.add_all([litigant1, litigant2])

        # 6. Courtrooms
        courtroom1 = Courtroom(
            courtroom_name="Courtroom 1 - Chief Justice Court",
            location="Building A, 1st Floor",
            capacity=80,
            availability=True
        )
        courtroom2 = Courtroom(
            courtroom_name="Courtroom 2 - Criminal Division Bench",
            location="Building A, 2nd Floor",
            capacity=60,
            availability=True
        )
        courtroom3 = Courtroom(
            courtroom_name="Courtroom 3 - Civil & Commercial Bench",
            location="Building B, 1st Floor",
            capacity=50,
            availability=True
        )
        courtroom4 = Courtroom(
            courtroom_name="Courtroom 4 - Family Court Bench",
            location="Building B, 2nd Floor",
            capacity=40,
            availability=True
        )
        session.add_all([courtroom1, courtroom2, courtroom3, courtroom4])

        # 7. AI Scheduler record
        ai_scheduler = AIScheduler(
            scheduling_model="ConstraintProgramming-CPSAT-v1",
            status="READY",
            configuration='{"max_daily_hearings_per_courtroom": 8, "working_hours_start": "10:30", "working_hours_end": "17:00"}'
        )
        session.add(ai_scheduler)

        # 8. Initial Audit Log
        audit = AuditLog(
            action="SYSTEM_INITIALIZATION",
            entity_type="SYSTEM",
            entity_id="0",
            details="System database initialized and seeded with default roles and courtrooms.",
            ip_address="127.0.0.1",
            date_time=datetime.utcnow()
        )
        session.add(audit)

        session.commit()
        print("Initial data seeded successfully!")
        print("Default users created with password 'Password@123'")
        print("- Admin: admin / admin@court.gov.in")
        print("- Clerk: clerk1 / clerk1@court.gov.in")
        print("- Judges: judge_sharma, judge_patel")
        print("- Lawyers: adv_verma, adv_rao")
        print("- Litigants: rajesh_k, sunita_d")
        print("=" * 60)

if __name__ == "__main__":
    init_database()
