from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    # Database
    DATABASE_URL: str = "sqlite:///news_database.db"
    
    # JWT
    JWT_SECRET_KEY: str = '1892dhianiandowqd0n'
    JWT_ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    
    # OpenAI
    OPENAI_API_KEY: str
    
    # Sentry
    SENTRY_DSN: str
    
    # CORS
    CORS_ORIGINS: list[str] = ["http://localhost:8080"]
    
    class Config:
        env_file = ".env"

settings = Settings()