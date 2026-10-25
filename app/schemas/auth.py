from pydantic import BaseModel, EmailStr
from typing import Optional, List
from datetime import datetime
from app.models.user import UserRole

class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user_id: int
    name: str
    email: str
    username: str
    role: UserRole

class LoginRequest(BaseModel):
    username_or_email: str
    password: str

class PasswordResetRequest(BaseModel):
    email: EmailStr

class PasswordResetConfirm(BaseModel):
    token: str
    new_password: str

class UserBase(BaseModel):
    name: str
    email: EmailStr
    mobile_no: str
    username: str
    role: UserRole

class UserCreate(UserBase):
    password: str
    # Role-specific fields
    admin_role: Optional[str] = "SUPER_ADMIN"
    employee_id: Optional[str] = None
    specialization: Optional[str] = "General"
    bar_registration_no: Optional[str] = None
    address: Optional[str] = None

class UserUpdateStatus(BaseModel):
    is_active: bool

class UserProfileResponse(BaseModel):
    user_id: int
    name: str
    email: str
    mobile_no: str
    username: str
    role: UserRole
    is_active: bool
    created_at: datetime
    # Role specific details
    admin_role: Optional[str] = None
    employee_id: Optional[str] = None
    specialization: Optional[str] = None
    availability: Optional[str] = None
    bar_registration_no: Optional[str] = None
    address: Optional[str] = None

    class Config:
        from_attributes = True
