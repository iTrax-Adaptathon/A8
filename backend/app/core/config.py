from typing import List, Union

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(case_sensitive=True, env_file=".env", extra="ignore")

    PROJECT_NAME: str = "FlowCare_2 — Hospital Capacity & Patient Flow Platform"
    API_V1_STR: str = "/api/v1"
    DATABASE_URL: str = "sqlite:///./flowcare_2.db"
    DEBUG: bool = True

    # Capacity Intelligence Configurable Thresholds
    HIGH_UTILIZATION_THRESHOLD: float = 75.0  # Occupancy % >= 75 triggers Warning
    CRITICAL_UTILIZATION_THRESHOLD: float = 90.0  # Occupancy % >= 90 triggers Critical Alert

    # Deterministic matching: automatically confirm the top-ranked eligible
    # waitlist candidate when a resource becomes AVAILABLE (can be overridden per request).
    AUTO_ASSIGN_ON_RELEASE: bool = True

    # CORS: comma-separated list of allowed frontend origins (env CORS_ORIGINS).
    CORS_ORIGINS: Union[List[str], str] = [
        "http://localhost:5173",
        "http://127.0.0.1:5173",
        "http://localhost:3000",
        "http://127.0.0.1:3000",
    ]

    @field_validator("CORS_ORIGINS", mode="before")
    @classmethod
    def _split_origins(cls, value):
        if isinstance(value, str):
            return [origin.strip() for origin in value.split(",") if origin.strip()]
        return value


settings = Settings()
