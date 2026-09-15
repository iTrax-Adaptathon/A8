from datetime import datetime
from typing import List, Optional
from app.api.schemas.base import CamelModel
from app.domain.enums import CapacityAlertLevel


class DepartmentUtilizationSchema(CamelModel):
    department_id: int
    department_name: str
    department_code: str
    total_beds: int
    occupied_beds: int
    available_beds: int
    cleaning_beds: int
    maintenance_beds: int
    occupancy_percentage: float
    alert_level: CapacityAlertLevel


class BedCapacitySchema(CamelModel):
    total: int
    available: int
    occupied: int
    cleaning: int
    maintenance: int


class TheatreCapacitySchema(CamelModel):
    total: int
    available: int
    in_use: int
    cleaning: int
    unavailable: int
    booked_slots: int
    available_slots: int
    next_available_slot: Optional[datetime] = None


class StaffCapacitySchema(CamelModel):
    total: int
    available: int
    assigned: int
    off_duty: int


class QueueCapacitySchema(CamelModel):
    waiting_for_beds: int
    waiting_for_theatres: int
    waiting_for_staff: int


class CapacityMetricsSchema(CamelModel):
    """Live capacity snapshot. `available` always means assignable right now."""

    total_beds: int
    occupied_beds: int
    available_beds: int
    overall_occupancy_percentage: float
    overall_alert_level: CapacityAlertLevel
    department_metrics: List[DepartmentUtilizationSchema]
    high_utilization_departments: List[str]
    critical_capacity_departments: List[str]
    beds: BedCapacitySchema
    theatres: TheatreCapacitySchema
    staff: StaffCapacitySchema
    queues: QueueCapacitySchema
    generated_at: datetime
