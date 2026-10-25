from fastapi import APIRouter
from app.api.v1.endpoints import (
    auth,
    users,
    dashboard,
    audit,
    cases,
    hearings,
    cause_list,
    virtual_court,
    tracking,
    notifications
)

api_router = APIRouter()

api_router.include_router(auth.router, prefix="/auth", tags=["Authentication & Access Control"])
api_router.include_router(users.router, prefix="/users", tags=["User Management"])
api_router.include_router(cases.router, prefix="/cases", tags=["Case & Evidence Management"])
api_router.include_router(hearings.router, prefix="/hearings", tags=["AI Scheduling & Hearing Management"])
api_router.include_router(cause_list.router, prefix="/cause-lists", tags=["Cause Lists & Calendar Management"])
api_router.include_router(virtual_court.router, prefix="/virtual-court", tags=["Virtual Courtroom & AI Transcription"])
api_router.include_router(tracking.router, prefix="/tracking", tags=["Hearing Tracking & WebSocket Gateway"])
api_router.include_router(notifications.router, prefix="/notifications", tags=["Smart Notifications & Reminders"])
api_router.include_router(dashboard.router, prefix="/dashboard", tags=["Role Dashboards"])
api_router.include_router(audit.router, prefix="/audit-logs", tags=["Audit Trail"])
