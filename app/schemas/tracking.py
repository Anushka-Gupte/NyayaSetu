from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import date, datetime

class HearingPostponeRequest(BaseModel):
    reason: str = Field(..., min_length=5)
    new_hearing_date: Optional[date] = None
    new_hearing_time: Optional[str] = None

class LiveHearingInfo(BaseModel):
    hearing_id: int
    case_id: int
    case_number: str
    case_title: str
    judge_name: str
    hearing_time: str
    hearing_status: str
    hearing_type: str

class CourtroomDisplayBoard(BaseModel):
    courtroom_id: int
    courtroom_name: str
    location: str
    bench_status: str # "IN_SESSION", "AVAILABLE", "ADJOURNED"
    current_matter: Optional[LiveHearingInfo] = None
    next_matter: Optional[LiveHearingInfo] = None
    today_total_matters: int = 0

class CaseTimelineMilestone(BaseModel):
    history_id: int
    event: str
    date_time: datetime
    description: str
    user_id: Optional[int] = None
    actor_name: Optional[str] = None

class CaseTimelineResponse(BaseModel):
    case_id: int
    case_number: str
    case_title: str
    case_status: str
    priority: str
    filing_date: date
    total_events: int
    timeline: List[CaseTimelineMilestone] = []
