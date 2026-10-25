from fastapi import APIRouter
from app.api.v1.endpoints import auth, users, dashboard, audit

api_router = APIRouter()

api_router.include_router(auth.router, prefix="/auth", tags=["Authentication & Access Control"])
api_router.include_router(users.router, prefix="/users", tags=["User Management"])
api_router.include_router(dashboard.router, prefix="/dashboard", tags=["Role Dashboards"])
api_router.include_router(audit.router, prefix="/audit-logs", tags=["Audit Trail"])
