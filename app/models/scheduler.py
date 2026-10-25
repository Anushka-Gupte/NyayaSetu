from datetime import datetime
from typing import Optional
from sqlalchemy import Integer, String, DateTime, Text, JSON
from sqlalchemy.orm import Mapped, mapped_column
from app.core.database import Base

class AIScheduler(Base):
    """AIScheduler entity corresponding to UML AIScheduler"""
    __tablename__ = "ai_schedulers"

    scheduler_id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True, index=True)
    scheduling_model: Mapped[str] = mapped_column(String(100), default="ConstraintProgramming-CPSAT-v1", nullable=False)
    last_run_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    status: Mapped[str] = mapped_column(String(50), default="IDLE", nullable=False)
    configuration: Mapped[Optional[str]] = mapped_column(Text, nullable=True) # JSON or config string
