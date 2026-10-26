from pydantic import BaseModel, EmailStr, Field, field_validator
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
    expected_role: Optional[UserRole] = None

class CitizenRegistrationRequest(BaseModel):
    """Public self-registration is limited to citizens; court roles stay admin-managed."""
    name: str = Field(min_length=2, max_length=120)
    email: EmailStr
    mobile_no: str = Field(min_length=10, max_length=20)
    username: str = Field(min_length=3, max_length=60, pattern=r"^[A-Za-z0-9_.-]+$")
    password: str = Field(min_length=10, max_length=72)
    address: str = Field(default="", max_length=255)

    @field_validator("name", "username", "mobile_no", "address", mode="before")
    @classmethod
    def trim_text(cls, value):
        return value.strip() if isinstance(value, str) else value

    @field_validator("mobile_no")
    @classmethod
    def validate_indian_mobile(cls, value):
        import re
        normalized = re.sub(r"[ -]", "", value)
        if not re.fullmatch(r"(?:\+91)?[6-9]\d{9}", normalized):
            raise ValueError("Enter a valid 10-digit Indian mobile number, optionally with +91.")
        return normalized

    @field_validator("password")
    @classmethod
    def validate_password_bytes(cls, value):
        if len(value.encode("utf-8")) > 72:
            raise ValueError("Password must be 72 bytes or fewer.")
        return value

class PasswordResetRequest(BaseModel):
    email: EmailStr

class PasswordResetConfirm(BaseModel):
    token: str
    new_password: str

class UserBase(BaseModel):
    name: str = Field(min_length=2, max_length=120)
    email: EmailStr
    mobile_no: str = Field(min_length=10, max_length=20)
    username: str = Field(min_length=3, max_length=60, pattern=r"^[A-Za-z0-9_.-]+$")
    role: UserRole

class UserCreate(UserBase):
    password: str = Field(min_length=10, max_length=72)
    # Role-specific fields
    admin_role: Optional[str] = "SUPER_ADMIN"
    employee_id: Optional[str] = None
    specialization: Optional[str] = "General"
    bar_registration_no: Optional[str] = None
    address: Optional[str] = None

    @field_validator("name", "username", "mobile_no", mode="before")
    @classmethod
    def trim_user_text(cls, value):
        return value.strip() if isinstance(value, str) else value

    @field_validator("mobile_no")
    @classmethod
    def validate_indian_mobile(cls, value):
        import re
        normalized = re.sub(r"[ -]", "", value)
        if not re.fullmatch(r"(?:\+91)?[6-9]\d{9}", normalized):
            raise ValueError("Enter a valid 10-digit Indian mobile number, optionally with +91.")
        return normalized

    @field_validator("password")
    @classmethod
    def validate_password_bytes(cls, value):
        if len(value.encode("utf-8")) > 72:
            raise ValueError("Password must be 72 bytes or fewer.")
        return value

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
