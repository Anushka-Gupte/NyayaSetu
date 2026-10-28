from pydantic import BaseModel
from typing import Optional, List
from datetime import datetime

class OnlineHearingCreate(BaseModel):
    hearing_id: int
    meeting_passcode: Optional[str] = None

class AttendanceRecordResponse(BaseModel):
    attendance_id: int
    online_hearing_id: int
    user_id: int
    user_name: str
    role: str
    joined_at: datetime
    left_at: Optional[datetime] = None

    class Config:
        from_attributes = True

class TranscriptResponse(BaseModel):
    transcript_id: int
    online_hearing_id: int
    generated_date: datetime
    transcript_text: str
    word_count: int

    class Config:
        from_attributes = True

class OnlineHearingResponse(BaseModel):
    online_hearing_id: int
    hearing_id: int
    case_number: str
    case_title: str
    meeting_link: str
    meeting_passcode: Optional[str] = None
    meeting_provider: str = "jitsi"
    start_time: Optional[datetime] = None
    end_time: Optional[datetime] = None
    is_recorded: bool
    recording_file_path: Optional[str] = None
    attendees_count: int = 0
    has_transcript: bool = False
    transcript_id: Optional[int] = None

    class Config:
        from_attributes = True

class JoinHearingResponse(BaseModel):
    online_hearing_id: int
    meeting_url: str
    room_name: str
    participant_name: str
    role: str
    meeting_provider: str = "jitsi"
