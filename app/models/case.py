from datetime import datetime, date
from typing import Optional, List
from sqlalchemy import Integer, String, Date, DateTime, Text, Boolean, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.core.database import Base

class CourtCase(Base):
    """CourtCase entity corresponding to UML CourtCase"""
    __tablename__ = "court_cases"

    case_id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True, index=True)
    case_number: Mapped[str] = mapped_column(String(50), unique=True, index=True, nullable=False)
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    case_type: Mapped[str] = mapped_column(String(100), nullable=False) # Civil, Criminal, Family, Commercial, etc.
    filing_date: Mapped[date] = mapped_column(Date, default=date.today, nullable=False)
    case_status: Mapped[str] = mapped_column(String(50), default="Registered", nullable=False) # Registered, Active, Pending, Disposed
    priority: Mapped[str] = mapped_column(String(30), default="Medium", nullable=False) # Low, Medium, High, Urgent
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Foreign Keys
    clerk_id: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("court_clerks.clerk_id"), nullable=True)
    litigant_id: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("litigants.litigant_id"), nullable=True)
    cause_list_id: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("cause_lists.cause_list_id"), nullable=True)

    # Relationships
    clerk = relationship("CourtClerk", back_populates="registered_cases")
    litigant = relationship("Litigant", back_populates="cases")
    lawyers = relationship("CaseLawyerAssociation", back_populates="case", cascade="all, delete-orphan")
    documents = relationship("CaseDocument", back_populates="case", cascade="all, delete-orphan")
    evidence = relationship("DigitalEvidence", back_populates="case", cascade="all, delete-orphan")
    history = relationship("CaseHistory", back_populates="case", cascade="all, delete-orphan")
    hearings = relationship("Hearing", back_populates="case", cascade="all, delete-orphan")
    notifications = relationship("Notification", back_populates="case", cascade="all, delete-orphan")
    cause_list = relationship("CauseList", back_populates="cases")


class CaseLawyerAssociation(Base):
    """Association table linking Lawyer (1..*) with CourtCase"""
    __tablename__ = "case_lawyer_associations"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    case_id: Mapped[int] = mapped_column(Integer, ForeignKey("court_cases.case_id"), nullable=False)
    lawyer_id: Mapped[int] = mapped_column(Integer, ForeignKey("lawyers.lawyer_id"), nullable=False)
    representing_party: Mapped[str] = mapped_column(String(50), default="Petitioner", nullable=False) # Petitioner, Respondent, Intervenor

    case = relationship("CourtCase", back_populates="lawyers")
    lawyer = relationship("Lawyer", back_populates="assigned_cases")


class CaseDocument(Base):
    """CaseDocument entity corresponding to UML CaseDocument"""
    __tablename__ = "case_documents"

    document_id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True, index=True)
    case_id: Mapped[int] = mapped_column(Integer, ForeignKey("court_cases.case_id"), nullable=False)
    document_name: Mapped[str] = mapped_column(String(200), nullable=False)
    document_type: Mapped[str] = mapped_column(String(100), nullable=False) # Petition, Affidavit, Order, ChargeSheet, etc.
    file_path: Mapped[str] = mapped_column(String(255), nullable=False)
    file_size_bytes: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    file_hash: Mapped[str] = mapped_column(String(64), nullable=False) # SHA-256 for integrity verification
    version: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    is_confidential: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    upload_date: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    uploaded_by_id: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("users.user_id"), nullable=True)

    case = relationship("CourtCase", back_populates="documents")


class DigitalEvidence(Base):
    """DigitalEvidence entity corresponding to UML DigitalEvidence"""
    __tablename__ = "digital_evidence"

    evidence_id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True, index=True)
    case_id: Mapped[int] = mapped_column(Integer, ForeignKey("court_cases.case_id"), nullable=False)
    evidence_type: Mapped[str] = mapped_column(String(50), nullable=False) # Audio, Video, Image, Document, Forensics
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    file_path: Mapped[str] = mapped_column(String(255), nullable=False)
    file_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    submission_date: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    submitted_by_id: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("users.user_id"), nullable=True)
    is_verified: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    case = relationship("CourtCase", back_populates="evidence")


class CaseHistory(Base):
    """CaseHistory entity corresponding to UML CaseHistory"""
    __tablename__ = "case_histories"

    history_id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True, index=True)
    case_id: Mapped[int] = mapped_column(Integer, ForeignKey("court_cases.case_id"), nullable=False)
    event: Mapped[str] = mapped_column(String(120), nullable=False)
    date_time: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    user_id: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("users.user_id"), nullable=True)

    case = relationship("CourtCase", back_populates="history")
