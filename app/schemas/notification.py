from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import datetime

class NotificationCreate(BaseModel):
    recipient_id: int
    case_id: Optional[int] = None
    notification_type: str = "In-App" # Email, SMS, In-App
    title: str = Field(..., min_length=3, max_length=200)
    message: str = Field(..., min_length=5)

class NotificationResponse(BaseModel):
    notification_id: int
    recipient_id: int
    recipient_name: Optional[str] = None
    case_id: Optional[int] = None
    notification_type: str
    title: str
    message: str
    date_time: datetime
    delivery_status: str
    is_read: bool

    class Config:
        from_attributes = True

class NotificationPreference(BaseModel):
    email_enabled: bool = True
    sms_enabled: bool = True
    in_app_enabled: bool = True

class NotificationStats(BaseModel):
    total_notifications: int
    sent_count: int
    delivered_count: int
    failed_count: int
    pending_count: int
    unread_count: int
