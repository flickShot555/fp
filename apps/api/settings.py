from pydantic_settings import BaseSettings
from pydantic import Field
import os
import dotenv; 

dotenv.load_dotenv()


class Settings(BaseSettings):
    GROQ_API_KEY: str = Field(default=os.getenv("GROQ_API_KEY", ""))
    GROQ_TEXT_MODEL: str = Field(default=os.getenv("GROQ_TEXT_MODEL", "llama-3.3-70b-versatile"))
    GROQ_VISION_MODEL: str = Field(default=os.getenv("GROQ_VISION_MODEL", "meta-llama/llama-4-scout-17b-16e-instruct"))

    DATA_DIR: str = Field(default=os.getenv("DATA_DIR", "./data"))
    APP_HOST: str = Field(default=os.getenv("APP_HOST", "0.0.0.0"))
    APP_PORT: int = Field(default=int(os.getenv("APP_PORT", "8000")))
    FMCSA_BASE_URL: str = Field(default=os.getenv("FMCSA_BASE_URL", "https://mobile.fmcsa.dot.gov/qc/services"))
    FMCSA_API_KEY: str = Field(default=os.getenv("FMCSA_API_KEY", ""))
    FMCSA_WEB_KEY: str = Field(default=os.getenv("FMCSA_WEB_KEY", ""))
    ALERT_WEBHOOK_URL: str = Field(default=os.getenv("ALERT_WEBHOOK_URL", ""))

    class Config:
        env_file = ".env"
        extra = "ignore"  # Ignore extra fields like VITE_API_URL


settings = Settings()
