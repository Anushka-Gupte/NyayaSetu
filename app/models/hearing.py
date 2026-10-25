from datetime import datetime, date, time
from typing import Optional, List
from sqlalchemy import Integer, String, Date, Time, DateTime, Text, Boolean, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.core.database import Base

class Courtroom(Base):
    """Courtroom entity corresponding to UML Courtroom"""
    __tablename__ = "courtrooms"

    courtroom_id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True, index=True)
    courtroom_name: Mapped[str] = mapped_column(String(100), unique=True, nullable=False)
    location: Mapped[str] = mapped_column(String(150), nullable=False)
    capacity: Mapped[int] = mapped_column(Integer, default=50, nullable=False)
    availability: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    # Relationships
    hearings = relationship("Hearing", back_populates="courtroom")


class Hearing(Base):
    """Hearing entity corresponding to UML Hearing"""
    __tablename__ = "hearings"

    hearing_id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True, index=True)
    case_id: Mapped[int] = mapped_column(Integer, ForeignKey("court_cases.case_id"), nullable=False)
    judge_id: Mapped[int] = mapped_column(Integer, ForeignKey("judges.judge_id"), nullable=False)
    courtroom_id: Mapped[int] = mapped_column(Integer, ForeignKey("courtrooms.courtroom_id"), nullable=False)
    
    hearing_date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    hearing_time: Mapped[time] = mapped_column(Time, nullable=False)
    hearing_status: Mapped[str] = mapped_column(String(40), default="Scheduled", nullable=False) 
    # Scheduled, In Progress, Completed, Adjourned, Postponed, Cancelled
    hearing_type: Mapped[str] = mapped_column(String(30), default="Physical", nullable=False) # Physical, Online, Hybrid
    
    adjournment_reason: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    outcome: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)

    # Relationships
    case = relationship("CourtCase", back_populates="hearings")
    judge = relationship("Judge", back_populates="hearings")
    courtroom = relationship("Courtroom", back_populates="hearings")
    online_hearing = relationship("OnlineHearing", back_populates="hearing", uselist=False, cascade="all, delete-orphan")


class OnlineHearing(Base):
    """OnlineHearing entity corresponding to UML OnlineHearing"""
    __tablename__ = "online_hearings"

    online_hearing_id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True, index=True)
    hearing_id: Mapped[int] = mapped_column(Integer, ForeignKey("hearings.hearing_id"), unique=True, nullable=False)
    meeting_link: Mapped[str] = mapped_column(String(255), nullable=False)
    meeting_passcode: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    start_time: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    end_time: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    is_recorded: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    recording_file_path: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)

    # Relationships
    hearing = relationship("Hearing", back_populates="online_hearing")
    transcript = relationship("Transcript", back_populates="online_hearing", uselist=False, cascade="all, delete-orphan")
    calendar_events = relationship("Calendar", back_populates="online_hearing", cascade="all, delete-orphan")
    attendees = relationship("HearingAttendance", back_populates="online_hearing", cascade="all, delete-orphan")


class HearingAttendance(Base):
    """Attendance log entity for Virtual Hearing (FR-4.6.3 VirtualHearing.Attendance.Track)"""
    __tablename__ = "hearing_attendees"

    attendance_id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True, index=True)
    online_hearing_id: Mapped[int] = mapped_column(Integer, ForeignKey("online_hearings.online_hearing_id"), nullable=False)
    user_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.user_id"), nullable=False)
    user_name: Mapped[str] = mapped_column(String(120), nullable=False)
    role: Mapped[str] = mapped_column(String(50), nullable=False)
    joined_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    left_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    ip_address: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)

    online_hearing = relationship("OnlineHearing", back_populates="attendees")
    user = relationship("User")


class Transcript(Base):
    """Transcript entity corresponding to UML Transcript (Composition with OnlineHearing)"""
    __tablename__ = "transcripts"

    transcript_id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True, index=True)
    online_hearing_id: Mapped[int] = mapped_column(Integer, ForeignKey("online_hearings.online_hearing_id"), unique=True, nullable=False)
    transcript_text: Mapped[str] = mapped_column(Text, nullable=False)
    generated_date: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)

    # Relationship
    online_hearing = relationship("OnlineHearing", back_populates="transcript")


class Calendar(Base):
    """Calendar entity corresponding to UML Calendar"""
    __tablename__ = "calendars"

    calendar_id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True, index=True)
    online_hearing_id: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("online_hearings.online_hearing_id"), nullable=True)
    event_id: Mapped[str] = mapped_column(String(100), unique=True, index=True, nullable=False)
    event_date: Mapped[date] = mapped_column(Date, nullable=False)
    event_time: Mapped[time] = mapped_column(Time, nullable=False)
    sync_status: Mapped[str] = mapped_column(String(30), default="synced", nullable=False) # synced, pending, failed

    # Relationship
    online_hearing = relationship("OnlineHearing", back_populates="calendar_events")
