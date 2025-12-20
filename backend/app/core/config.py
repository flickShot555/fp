"""Application configuration settings."""
from pydantic_settings import BaseSettings
from pydantic import Field
from typing import List
import os


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""
    
    # Database
    DATABASE_URL: str = Field(default="postgresql+asyncpg://postgres:password@localhost:5432/freightpower")
    DATABASE_URL_SYNC: str = Field(default="postgresql://postgres:password@localhost:5432/freightpower")
    
    # Redis
    REDIS_URL: str = Field(default="redis://localhost:6379/0")
    
    # JWT
    JWT_SECRET_KEY: str = Field(default="super-secret-key-change-in-production")
    JWT_ALGORITHM: str = Field(default="HS256")
    ACCESS_TOKEN_EXPIRE_MINUTES: int = Field(default=30)
    REFRESH_TOKEN_EXPIRE_DAYS: int = Field(default=7)
    
    # Firebase
    FIREBASE_CREDENTIALS_PATH: str = Field(default="./firebase-credentials.json")
    
    # Twilio
    TWILIO_ACCOUNT_SID: str = Field(default="")
    TWILIO_AUTH_TOKEN: str = Field(default="")
    TWILIO_PHONE_NUMBER: str = Field(default="")
    
    # SendGrid
    SENDGRID_API_KEY: str = Field(default="")
    SENDGRID_FROM_EMAIL: str = Field(default="noreply@freightpower.ai")
    
    # FMCSA
    FMCSA_BASE_URL: str = Field(default="https://mobile.fmcsa.dot.gov/qc/services")
    FMCSA_WEB_KEY: str = Field(default="")
    FMCSA_API_KEY: str = Field(default="")
    
    # Groq AI
    GROQ_API_KEY: str = Field(default="")
    GROQ_TEXT_MODEL: str = Field(default="llama-3.3-70b-versatile")
    GROQ_VISION_MODEL: str = Field(default="meta-llama/llama-4-scout-17b-16e-instruct")
    
    # AWS S3
    AWS_ACCESS_KEY_ID: str = Field(default="")
    AWS_SECRET_ACCESS_KEY: str = Field(default="")
    AWS_S3_BUCKET: str = Field(default="freightpower-documents")
    AWS_REGION: str = Field(default="us-east-1")
    
    # Application
    APP_HOST: str = Field(default="0.0.0.0")
    APP_PORT: int = Field(default=5000)
    FRONTEND_URL: str = Field(default="http://localhost:5173")
    DEBUG: bool = Field(default=True)
    
    # CORS
    CORS_ORIGINS: List[str] = ["http://localhost:5173", "http://localhost:3000"]
    
    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        extra = "ignore"


settings = Settings()

