from datetime import datetime, date
from typing import Optional, List
from sqlalchemy import Integer, String, Date, DateTime, Boolean, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.core.database import Base

class CauseList(Base):
    """CauseList entity corresponding to UML CauseList"""
    __tablename__ = "cause_lists"

    cause_list_id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True, index=True)
    date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    court_name: Mapped[str] = mapped_column(String(150), nullable=False)
    is_published: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    generated_date: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    published_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    pdf_path: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)

    # Relationships
    cases = relationship("CourtCase", back_populates="cause_list")
