import os

import app.models  # Register every model with SQLAlchemy metadata.
from app.core.database import Base, SessionLocal, engine
from app.core.security import get_password_hash
from app.models.user import Administrator, User, UserRole


def init_database():
    print("Creating database schema...")
    Base.metadata.create_all(bind=engine)

    with SessionLocal() as session:
        existing_admin = session.query(User).filter(User.username == "admin").first()
        if existing_admin:
            print("Bootstrap administrator already exists; no sample records were added.")
            return

        password = os.getenv("BOOTSTRAP_ADMIN_PASSWORD", "Password@123")
        admin = Administrator(
            name=os.getenv("BOOTSTRAP_ADMIN_NAME", "System Administrator"),
            email=os.getenv("BOOTSTRAP_ADMIN_EMAIL", "admin@court.gov.in"),
            mobile_no=os.getenv("BOOTSTRAP_ADMIN_MOBILE", "9876543210"),
            username="admin",
            password=get_password_hash(password),
            role=UserRole.ADMINISTRATOR,
            admin_role="SUPER_ADMIN"
        )
        session.add(admin)
        session.commit()
        print("Bootstrap administrator created. No sample users, cases, hearings, or courtrooms were added.")


if __name__ == "__main__":
    init_database()
