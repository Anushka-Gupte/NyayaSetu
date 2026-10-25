from datetime import datetime
from typing import Optional
from sqlalchemy import Integer, String, DateTime, Text, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.core.database import Base

class Notification(Base):
    """Notification entity corresponding to UML Notification"""
    __tablename__ = "notifications"

    notification_id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True, index=True)
    recipient_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.user_id"), nullable=False)
    case_id: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("court_cases.case_id"), nullable=True)
    
    notification_type: Mapped[str] = mapped_column(String(30), nullable=False) # Email, SMS, In-App
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    message: Mapped[str] = mapped_column(Text, nullable=False)
    date_time: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    delivery_status: Mapped[str] = mapped_column(String(30), default="Pending", nullable=False) # Pending, Sent, Delivered, Failed
    is_read: Mapped[bool] = mapped_column(default=False, nullable=False)

    # Relationships
    recipient = relationship("User", back_populates="notifications")
    case = relationship("CourtCase", back_populates="notifications")
