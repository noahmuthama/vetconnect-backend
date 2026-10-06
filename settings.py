from functools import lru_cache
from typing import Literal

from pydantic import Field, SecretStr, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Runtime configuration loaded from environment variables or .env."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    app_name: str = "VetConnect API"
    environment: Literal["development", "testing", "staging", "production"] = "development"
    database_url: str = "sqlite:///./vet_connect.db"
    jwt_secret_key: SecretStr = Field(default=SecretStr("dev-only-change-me"), min_length=16)
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = Field(default=60, ge=5, le=1440)
    cors_origins: list[str] = ["http://localhost:3000", "http://localhost:5173"]
    max_nearby_radius_km: float = Field(default=100.0, gt=0, le=500)
    rate_limit_per_minute: int = Field(default=60, ge=1, le=10000)

    @field_validator("database_url")
    @classmethod
    def normalize_database_url(cls, value: str) -> str:
        # Render/Heroku-style PostgreSQL URLs use postgres://, while SQLAlchemy
        # expects postgresql://.
        if value.startswith("postgres://"):
            return "postgresql://" + value[len("postgres://") :]
        return value

    @field_validator("jwt_secret_key")
    @classmethod
    def reject_weak_production_secret(cls, value: SecretStr, info) -> SecretStr:
        environment = info.data.get("environment", "development")
        if environment == "production" and value.get_secret_value() == "dev-only-change-me":
            raise ValueError("JWT_SECRET_KEY must be changed in production")
        return value


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
