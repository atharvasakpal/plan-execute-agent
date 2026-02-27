"""
Configuration management using Pydantic settings
Loads from environment variables or .env file
"""

from pydantic_settings import BaseSettings
from typing import List

class Settings(BaseSettings):
    # API Configuration
    GOOGLE_API_KEY: str
    TAVILY_API_KEY: str  # Added for Tavily search
    ENVIRONMENT: str = "development"  # development, staging, production
    
    # CORS
    ALLOWED_ORIGINS: List[str] = ["*"]
    
    # Agent Configuration
    MODEL_NAME: str = "gemini-2.5-flash"
    MODEL_TEMPERATURE: float = 1.0
    MAX_RETRIES: int = 3
    TIMEOUT_SECONDS: int = 300
    
    # AWS Configuration (optional)
    AWS_REGION: str = "us-east-1"
    
    class Config:
        env_file = ".env"
        case_sensitive = True

settings = Settings()