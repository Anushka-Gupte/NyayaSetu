import os
from pydantic_settings import BaseSettings
from typing import Optional

class Settings(BaseSettings):
    PROJECT_NAME: str = "NyayaSetu - Court Case Scheduling & Hearing Management System"
    APP_BASE_URL: str = "http://localhost:8000"
    ENVIRONMENT: str = "development"
    API_V1_STR: str = "/api/v1"
    SECRET_KEY: str
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 120
    SESSION_IDLE_TIMEOUT_MINUTES: int = 30
    CORS_ORIGINS: list[str] = ["http://localhost:8000", "http://127.0.0.1:8000"]
    
    # Database
    DATABASE_URL: str = "sqlite:///./nyayasetu.db"
    
    # File Storage
    UPLOAD_DIR: str = "./uploads"
    MAX_FILE_SIZE_MB: int = 50
    
    # Virtual Court & AI
    VIRTUAL_COURT_BASE_URL: str = "https://meet.jit.si"
    VIRTUAL_COURT_PROVIDER: str = "jitsi"
    GOOGLE_MEET_CLIENT_ID: Optional[str] = None
    GOOGLE_MEET_CLIENT_SECRET: Optional[str] = None
    GOOGLE_MEET_REFRESH_TOKEN: Optional[str] = None
    WHISPER_MODEL_SIZE: str = "base"

    # Outbound notification providers (leave unset to record a failed delivery attempt).
    SMTP_HOST: Optional[str] = None
    SMTP_PORT: int = 587
    SMTP_USERNAME: Optional[str] = None
    SMTP_PASSWORD: Optional[str] = None
    SMTP_FROM_EMAIL: Optional[str] = None
    SMTP_USE_TLS: bool = True
    SMTP_USE_SSL: bool = False
    TWILIO_ACCOUNT_SID: Optional[str] = None
    TWILIO_AUTH_TOKEN: Optional[str] = None
    TWILIO_FROM_NUMBER: Optional[str] = None

    class Config:
        env_file = ".env"
        extra = "ignore"

settings = Settings()
