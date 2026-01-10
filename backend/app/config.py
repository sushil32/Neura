"""Application configuration using Pydantic settings."""
from functools import lru_cache
from typing import List, Optional

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    model_config = SettingsConfigDict(
        env_file=".env.local",
        env_file_encoding="utf-8",
        case_sensitive=False,
    )

    # Environment
    env: str = "local"
    debug: bool = True

    # Database
    postgres_host: str = "localhost"
    postgres_port: int = 5433
    postgres_db: str = "neura"
    postgres_user: str = "neura"
    postgres_password: str = "neura_dev_password"
    database_url: Optional[str] = None

    @property
    def db_url(self) -> str:
        """Get database URL, constructing from components if not provided."""
        if self.database_url:
            return self.database_url
        return (
            f"postgresql+asyncpg://{self.postgres_user}:{self.postgres_password}"
            f"@{self.postgres_host}:{self.postgres_port}/{self.postgres_db}"
        )

    @property
    def sync_db_url(self) -> str:
        """Get synchronous database URL for Alembic migrations."""
        return self.db_url.replace("postgresql+asyncpg", "postgresql+psycopg2")

    # Redis
    redis_url: str = "redis://localhost:6379/0"
    celery_broker_url: str = "redis://localhost:6379/1"
    celery_result_backend: str = "redis://localhost:6379/2"

    # S3/MinIO
    s3_endpoint: str = "http://localhost:9000"  # Internal endpoint for backend
    s3_public_endpoint: str = "http://localhost:9000"  # Public endpoint for frontend
    s3_access_key: str = "neura_minio"
    s3_secret_key: str = "neura_minio_password"
    s3_bucket: str = "neura-storage"
    s3_region: str = "us-east-1"

    # JWT
    jwt_secret_key: str = "dev-secret-key-change-in-production-minimum-32-chars"
    jwt_algorithm: str = "HS256"
    jwt_access_token_expire_minutes: int = 30
    jwt_refresh_token_expire_days: int = 7

    # LLM
    llm_provider: str = "lmstudio"
    lmstudio_base_url: str = "http://localhost:1234/v1"
    gemini_api_key: Optional[str] = None

    # TTS
    tts_provider: str = "neura"
    tts_model_path: str = "/app/models/tts"

    # CORS
    cors_origins: str = "http://localhost:3000"

    @property
    def cors_origins_list(self) -> List[str]:
        """Parse CORS origins string to list."""
        return [origin.strip() for origin in self.cors_origins.split(",")]

    # Rate limiting
    rate_limit_requests: int = 100
    rate_limit_window: int = 60  # seconds


@lru_cache()
def get_settings() -> Settings:
    """Get cached settings instance."""
    return Settings()


settings = get_settings()

