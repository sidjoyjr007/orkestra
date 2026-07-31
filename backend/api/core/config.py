from pydantic_settings import BaseSettings, SettingsConfigDict
from typing import Optional

class Settings(BaseSettings):
    # App Settings
    PROJECT_NAME: str = "Orkestra Control Plane"
    VERSION: str = "1.0.0"
    API_V1_STR: str = "/api"
    
    # Auth & Security
    SECRET_KEY: str = "your-super-secret-key-change-in-production"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    # Fernet key must be 32 url-safe base64-encoded bytes. 
    ENCRYPTION_KEY: str = "T83mD_R6X22g-KjO0Z4yWfN_k9c81I3y_y5R2JzBqQc="
    REFRESH_TOKEN_EXPIRE_DAYS: int = 7
    
    # Database
    AUTH_DATABASE_URL: str = "postgresql+asyncpg://orkestra:orkestra_secret@localhost:5433/orkestra_state"
    
    # Frontend Config
    FRONTEND_URL: str = "http://localhost:5173"
    ALLOWED_ORIGINS: list[str] = [
        "http://localhost:5173", 
        "http://localhost:3000",
        "http://127.0.0.1:5173",
        "http://127.0.0.1:3000",
        "http://localhost:5174",
        "http://127.0.0.1:5174"
    ]

    model_config = SettingsConfigDict(
        env_file=".env", 
        env_file_encoding="utf-8", 
        case_sensitive=True,
        extra="ignore"
    )

settings = Settings()
