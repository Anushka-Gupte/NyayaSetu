import enum
from datetime import datetime
from typing import Optional
from sqlalchemy import Integer, String, Boolean, DateTime, ForeignKey, Enum as SQLEnum
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.core.database import Base

class UserRole(str, enum.Enum):
    ADMINISTRATOR = "ADMINISTRATOR"
    COURT_CLERK = "COURT_CLERK"
    JUDGE = "JUDGE"
    LAWYER = "LAWYER"
    LITIGANT = "LITIGANT"

class User(Base):
    """Abstract User Base Class corresponding to UML User (Abstract)"""
    __tablename__ = "users"

    user_id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True, index=True)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    email: Mapped[str] = mapped_column(String(120), unique=True, index=True, nullable=False)
    mobile_no: Mapped[str] = mapped_column(String(20), nullable=False)
    username: Mapped[str] = mapped_column(String(60), unique=True, index=True, nullable=False)
    password: Mapped[str] = mapped_column(String(255), nullable=False)
    role: Mapped[UserRole] = mapped_column(SQLEnum(UserRole), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)

    __mapper_args__ = {
        "polymorphic_on": "role",
        "polymorphic_identity": "USER",
    }

    # Relationship to audit logs and notifications
    notifications = relationship("Notification", back_populates="recipient", cascade="all, delete-orphan")
    audit_logs = relationship("AuditLog", back_populates="user")


class Administrator(User):
    """Administrator Subclass corresponding to UML Administrator"""
    __tablename__ = "administrators"

    admin_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.user_id"), primary_key=True)
    admin_role: Mapped[str] = mapped_column(String(50), default="SUPER_ADMIN", nullable=False)

    __mapper_args__ = {
        "polymorphic_identity": UserRole.ADMINISTRATOR,
    }


class CourtClerk(User):
    """Court Clerk Subclass corresponding to UML CourtClerk"""
    __tablename__ = "court_clerks"

    clerk_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.user_id"), primary_key=True)
    employee_id: Mapped[str] = mapped_column(String(50), unique=True, nullable=False)

    # Relationships
    registered_cases = relationship("CourtCase", back_populates="clerk")

    __mapper_args__ = {
        "polymorphic_identity": UserRole.COURT_CLERK,
    }


class Judge(User):
    """Judge Subclass corresponding to UML Judge"""
    __tablename__ = "judges"

    judge_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.user_id"), primary_key=True)
    specialization: Mapped[str] = mapped_column(String(100), nullable=False, default="General")
    availability: Mapped[str] = mapped_column(String(50), nullable=False, default="Available")

    # Relationships
    hearings = relationship("Hearing", back_populates="judge")

    __mapper_args__ = {
        "polymorphic_identity": UserRole.JUDGE,
    }


class Lawyer(User):
    """Lawyer Subclass corresponding to UML Lawyer"""
    __tablename__ = "lawyers"

    lawyer_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.user_id"), primary_key=True)
    bar_registration_no: Mapped[str] = mapped_column(String(80), unique=True, nullable=False)

    # Relationships
    assigned_cases = relationship("CaseLawyerAssociation", back_populates="lawyer")

    __mapper_args__ = {
        "polymorphic_identity": UserRole.LAWYER,
    }


class Litigant(User):
    """Litigant Subclass corresponding to UML Litigant"""
    __tablename__ = "litigants"

    litigant_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.user_id"), primary_key=True)
    address: Mapped[str] = mapped_column(String(255), nullable=False)

    # Relationships
    cases = relationship("CourtCase", back_populates="litigant")

    __mapper_args__ = {
        "polymorphic_identity": UserRole.LITIGANT,
    }
