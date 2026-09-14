from pydantic import ConfigDict
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    model_config = ConfigDict(case_sensitive=True)

    PROJECT_NAME: str = "FlowCare_2 — Hospital Capacity & Patient Flow Platform"
    API_V1_STR: str = "/api/v1"
    DATABASE_URL: str = "sqlite:///./flowcare_2.db"
    DEBUG: bool = True

    # Capacity Intelligence Configurable Thresholds
    HIGH_UTILIZATION_THRESHOLD: float = 75.0  # Occupancy % >= 75 triggers Warning
    CRITICAL_UTILIZATION_THRESHOLD: float = 90.0  # Occupancy % >= 90 triggers Critical Alert


settings = Settings()
