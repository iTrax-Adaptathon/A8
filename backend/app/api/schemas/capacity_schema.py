from typing import List
from pydantic import BaseModel, ConfigDict
from app.domain.enums import CapacityAlertLevel


class DepartmentUtilizationSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    department_id: int
    department_name: str
    department_code: str
    total_beds: int
    occupied_beds: int
    available_beds: int
    occupancy_percentage: float
    alert_level: CapacityAlertLevel


class CapacityMetricsSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    total_beds: int
    occupied_beds: int
    available_beds: int
    overall_occupancy_percentage: float
    overall_alert_level: CapacityAlertLevel
    department_metrics: List[DepartmentUtilizationSchema]
    high_utilization_departments: List[str]
    critical_capacity_departments: List[str]
