import os
from pydantic_settings import BaseSettings
from typing import Optional

class Settings(BaseSettings):
    PROJECT_NAME: str = "NyayaSetu - Court Case Scheduling & Hearing Management System"
    ENVIRONMENT: str = "development"
    API_V1_STR: str = "/api/v1"
    SECRET_KEY: str = "nyayasetu_secure_jwt_secret_key_development_judicial_2026_demo"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 120
    
    # Database
    DATABASE_URL: str = "sqlite:///./nyayasetu.db"
    
    # File Storage
    UPLOAD_DIR: str = "./uploads"
    MAX_FILE_SIZE_MB: int = 50
    
    # Virtual Court & AI
    VIRTUAL_COURT_BASE_URL: str = "https://meet.jit.si"
    WHISPER_MODEL_SIZE: str = "base"

    class Config:
        env_file = ".env"
        extra = "ignore"

settings = Settings()
