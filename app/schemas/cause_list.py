from pydantic import BaseModel
from typing import Optional, List
from datetime import date, datetime

class CauseListEntry(BaseModel):
    hearing_id: int
    case_id: int
    case_number: str
    case_title: str
    case_type: str
    priority: str
    hearing_time: str
    judge_name: str
    courtroom_name: str
    courtroom_location: str
    hearing_type: str
    hearing_status: str

class CauseListGenerateRequest(BaseModel):
    date: date
    court_name: str = "Principal District & Sessions Court, Mumbai"

class CauseListResponse(BaseModel):
    cause_list_id: int
    date: date
    court_name: str
    is_published: bool
    generated_date: datetime
    published_at: Optional[datetime] = None
    pdf_url: Optional[str] = None
    total_cases: int
    entries: List[CauseListEntry] = []

    class Config:
        from_attributes = True

class CalendarEventResponse(BaseModel):
    event_id: str
    hearing_id: int
    case_id: int
    case_number: str
    title: str
    hearing_date: date
    start_time: str
    end_time: str
    courtroom_name: str
    judge_name: str
    hearing_type: str
    status: str
