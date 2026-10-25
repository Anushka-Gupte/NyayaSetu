from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import date, time, datetime

class CourtroomBase(BaseModel):
    courtroom_name: str
    location: str
    capacity: int = 50
    availability: bool = True

class CourtroomResponse(CourtroomBase):
    courtroom_id: int

    class Config:
        from_attributes = True

class HearingSlotRecommendation(BaseModel):
    hearing_date: date
    hearing_time: str
    judge_id: int
    judge_name: str
    judge_specialization: str
    courtroom_id: int
    courtroom_name: str
    courtroom_location: str
    confidence_score: float
    reasons: List[str]

class HearingRecommendationRequest(BaseModel):
    case_id: int
    hearing_type: str = "Physical" # Physical, Online, Hybrid
    days_ahead_start: Optional[int] = None
    days_ahead_end: Optional[int] = None

class HearingRecommendationResponse(BaseModel):
    case_id: int
    case_number: str
    case_title: str
    case_type: str
    priority: str
    recommendations: List[HearingSlotRecommendation]

class HearingScheduleCreate(BaseModel):
    case_id: int
    judge_id: int
    courtroom_id: int
    hearing_date: date
    hearing_time: str # "HH:MM" e.g. "11:30"
    hearing_type: str = "Physical" # Physical, Online, Hybrid
    is_ai_recommended: bool = False
    notes: Optional[str] = None

class HearingRescheduleRequest(BaseModel):
    new_date: date
    new_time: str # "HH:MM"
    new_courtroom_id: Optional[int] = None
    new_judge_id: Optional[int] = None
    reason: str = Field(..., min_length=5)

class HearingCancelRequest(BaseModel):
    reason: str = Field(..., min_length=5)

class HearingAdjournRequest(BaseModel):
    reason: str = Field(..., min_length=5)
    next_hearing_date: Optional[date] = None
    next_hearing_time: Optional[str] = None

class HearingCompleteRequest(BaseModel):
    outcome: str = Field(..., min_length=5)

class ConflictCheckRequest(BaseModel):
    case_id: int
    judge_id: int
    courtroom_id: int
    hearing_date: date
    hearing_time: str
    exclude_hearing_id: Optional[int] = None

class ConflictCheckResponse(BaseModel):
    has_conflict: bool
    conflicts: List[str]
    suggested_alternatives: List[HearingSlotRecommendation] = []

class HearingResponse(BaseModel):
    hearing_id: int
    case_id: int
    case_number: str
    case_title: str
    judge_id: int
    judge_name: str
    courtroom_id: int
    courtroom_name: str
    courtroom_location: str
    hearing_date: date
    hearing_time: str
    hearing_status: str # Scheduled, In Progress, Completed, Adjourned, Postponed, Cancelled
    hearing_type: str
    adjournment_reason: Optional[str] = None
    outcome: Optional[str] = None
    created_at: datetime

    class Config:
        from_attributes = True
