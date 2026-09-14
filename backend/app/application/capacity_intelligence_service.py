from dataclasses import dataclass
from typing import List
from app.infrastructure.repositories import BedRepository, DepartmentRepository
from app.domain.enums import BedStatus, CapacityAlertLevel
from app.domain.policies import CapacityPolicy


@dataclass
class DepartmentUtilizationMetrics:
    department_id: int
    department_name: str
    department_code: str
    total_beds: int
    occupied_beds: int
    available_beds: int
    occupancy_percentage: float
    alert_level: CapacityAlertLevel


@dataclass
class HospitalCapacityMetrics:
    total_beds: int
    occupied_beds: int
    available_beds: int
    overall_occupancy_percentage: float
    overall_alert_level: CapacityAlertLevel
    department_metrics: List[DepartmentUtilizationMetrics]
    high_utilization_departments: List[str]
    critical_capacity_departments: List[str]


class CapacityIntelligenceService:
    def __init__(self, bed_repo: BedRepository, department_repo: DepartmentRepository):
        self.bed_repo = bed_repo
        self.department_repo = department_repo

    def calculate_hospital_capacity(self) -> HospitalCapacityMetrics:
        departments = self.department_repo.get_all()
        dept_metrics: List[DepartmentUtilizationMetrics] = []

        total_hospital_beds = 0
        total_hospital_occupied = 0

        high_util_depts: List[str] = []
        critical_depts: List[str] = []

        for dept in departments:
            t_beds = dept.total_beds
            o_beds = dept.occupied_beds
            a_beds = max(0, t_beds - o_beds)
            occupancy_pct = CapacityPolicy.calculate_utilization_percentage(t_beds, o_beds)
            alert = CapacityPolicy.evaluate_alert_level(occupancy_pct)

            if alert == CapacityAlertLevel.HIGH_UTILIZATION:
                high_util_depts.append(dept.name)
            elif alert == CapacityAlertLevel.CRITICAL_CAPACITY:
                critical_depts.append(dept.name)

            total_hospital_beds += t_beds
            total_hospital_occupied += o_beds

            dept_metrics.append(
                DepartmentUtilizationMetrics(
                    department_id=dept.id or 0,
                    department_name=dept.name,
                    department_code=dept.code,
                    total_beds=t_beds,
                    occupied_beds=o_beds,
                    available_beds=a_beds,
                    occupancy_percentage=occupancy_pct,
                    alert_level=alert,
                )
            )

        total_avail_beds = max(0, total_hospital_beds - total_hospital_occupied)
        overall_pct = CapacityPolicy.calculate_utilization_percentage(total_hospital_beds, total_hospital_occupied)
        overall_alert = CapacityPolicy.evaluate_alert_level(overall_pct)

        return HospitalCapacityMetrics(
            total_beds=total_hospital_beds,
            occupied_beds=total_hospital_occupied,
            available_beds=total_avail_beds,
            overall_occupancy_percentage=overall_pct,
            overall_alert_level=overall_alert,
            department_metrics=dept_metrics,
            high_utilization_departments=high_util_depts,
            critical_capacity_departments=critical_depts,
        )
