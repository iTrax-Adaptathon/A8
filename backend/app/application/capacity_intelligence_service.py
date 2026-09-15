"""Capacity snapshot built from COUNT queries over the current database state.

AVAILABLE always means "actually assignable right now": CLEANING, MAINTENANCE,
UNAVAILABLE, IN_USE and inactive resources are never counted as available.
"""
from dataclasses import dataclass, field
from datetime import datetime
from typing import List, Optional

from app.infrastructure.repositories import (
    BedRepository,
    DepartmentRepository,
    StaffRepository,
    TheatreRepository,
    TheatreSlotRepository,
    WaitlistRepository,
)
from app.domain.enums import (
    BedStatus,
    CapacityAlertLevel,
    StaffStatus,
    TheatreSlotStatus,
    TheatreStatus,
    WaitlistResourceType,
)
from app.domain.policies import CapacityPolicy, utc_now


@dataclass
class DepartmentUtilizationMetrics:
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


@dataclass
class BedCapacity:
    total: int
    available: int
    occupied: int
    cleaning: int
    maintenance: int


@dataclass
class TheatreCapacity:
    total: int
    available: int
    in_use: int
    cleaning: int
    unavailable: int
    booked_slots: int
    available_slots: int
    next_available_slot: Optional[datetime]


@dataclass
class StaffCapacity:
    total: int
    available: int
    assigned: int
    off_duty: int


@dataclass
class QueueCapacity:
    waiting_for_beds: int
    waiting_for_theatres: int
    waiting_for_staff: int


@dataclass
class HospitalCapacityMetrics:
    # Inherited top-level fields (kept for compatibility)
    total_beds: int
    occupied_beds: int
    available_beds: int
    overall_occupancy_percentage: float
    overall_alert_level: CapacityAlertLevel
    department_metrics: List[DepartmentUtilizationMetrics]
    high_utilization_departments: List[str]
    critical_capacity_departments: List[str]
    # Frontend-friendly groups
    beds: BedCapacity
    theatres: TheatreCapacity
    staff: StaffCapacity
    queues: QueueCapacity
    generated_at: datetime = field(default_factory=utc_now)


class CapacityIntelligenceService:
    def __init__(
        self,
        bed_repo: BedRepository,
        department_repo: DepartmentRepository,
        theatre_repo: Optional[TheatreRepository] = None,
        slot_repo: Optional[TheatreSlotRepository] = None,
        staff_repo: Optional[StaffRepository] = None,
        waitlist_repo: Optional[WaitlistRepository] = None,
    ):
        db = bed_repo.db
        self.bed_repo = bed_repo
        self.department_repo = department_repo
        self.theatre_repo = theatre_repo or TheatreRepository(db)
        self.slot_repo = slot_repo or TheatreSlotRepository(db)
        self.staff_repo = staff_repo or StaffRepository(db)
        self.waitlist_repo = waitlist_repo or WaitlistRepository(db)

    def calculate_hospital_capacity(self) -> HospitalCapacityMetrics:
        departments = self.department_repo.get_all()
        dept_metrics: List[DepartmentUtilizationMetrics] = []
        high_util_depts: List[str] = []
        critical_depts: List[str] = []

        for dept in departments:
            counts = self.department_repo.bed_status_counts(dept.id)
            t_beds = sum(counts.values())
            o_beds = counts[BedStatus.OCCUPIED.value]
            a_beds = counts[BedStatus.AVAILABLE.value]
            occupancy_pct = CapacityPolicy.calculate_utilization_percentage(t_beds, o_beds)
            alert = CapacityPolicy.evaluate_alert_level(occupancy_pct)

            if alert == CapacityAlertLevel.HIGH_UTILIZATION:
                high_util_depts.append(dept.name)
            elif alert == CapacityAlertLevel.CRITICAL_CAPACITY:
                critical_depts.append(dept.name)

            dept_metrics.append(
                DepartmentUtilizationMetrics(
                    department_id=dept.id or 0,
                    department_name=dept.name,
                    department_code=dept.code,
                    total_beds=t_beds,
                    occupied_beds=o_beds,
                    available_beds=a_beds,
                    cleaning_beds=counts[BedStatus.CLEANING.value],
                    maintenance_beds=counts[BedStatus.MAINTENANCE.value],
                    occupancy_percentage=occupancy_pct,
                    alert_level=alert,
                )
            )

        bed_counts = self.bed_repo.count_by_status()
        beds = BedCapacity(
            total=sum(bed_counts.values()),
            available=bed_counts[BedStatus.AVAILABLE.value],
            occupied=bed_counts[BedStatus.OCCUPIED.value],
            cleaning=bed_counts[BedStatus.CLEANING.value],
            maintenance=bed_counts[BedStatus.MAINTENANCE.value],
        )
        overall_pct = CapacityPolicy.calculate_utilization_percentage(beds.total, beds.occupied)
        overall_alert = CapacityPolicy.evaluate_alert_level(overall_pct)

        theatre_counts = self.theatre_repo.count_by_status()
        now = utc_now()
        available_theatre_ids = [t.id for t in self.theatre_repo.get_all(status=TheatreStatus.AVAILABLE)]
        next_slot = self.slot_repo.next_available_slot(now, available_theatre_ids) if available_theatre_ids else None
        theatres = TheatreCapacity(
            total=sum(theatre_counts.values()),
            available=theatre_counts[TheatreStatus.AVAILABLE.value],
            in_use=theatre_counts[TheatreStatus.IN_USE.value],
            cleaning=theatre_counts[TheatreStatus.CLEANING.value],
            unavailable=theatre_counts[TheatreStatus.UNAVAILABLE.value],
            booked_slots=self.slot_repo.count(status=TheatreSlotStatus.BOOKED),
            available_slots=self.slot_repo.count(status=TheatreSlotStatus.AVAILABLE, start_from=now),
            next_available_slot=next_slot.start_time if next_slot else None,
        )

        staff_counts = self.staff_repo.count_by_status()
        staff = StaffCapacity(
            total=sum(staff_counts.values()),
            available=staff_counts[StaffStatus.AVAILABLE.value],
            assigned=staff_counts[StaffStatus.ASSIGNED.value],
            off_duty=staff_counts[StaffStatus.OFF_DUTY.value],
        )

        waiting = self.waitlist_repo.waiting_counts_by_resource_type()
        queues = QueueCapacity(
            waiting_for_beds=waiting[WaitlistResourceType.BED.value],
            waiting_for_theatres=waiting[WaitlistResourceType.THEATRE.value],
            waiting_for_staff=waiting[WaitlistResourceType.STAFF.value],
        )

        return HospitalCapacityMetrics(
            total_beds=beds.total,
            occupied_beds=beds.occupied,
            available_beds=beds.available,
            overall_occupancy_percentage=overall_pct,
            overall_alert_level=overall_alert,
            department_metrics=dept_metrics,
            high_utilization_departments=high_util_depts,
            critical_capacity_departments=critical_depts,
            beds=beds,
            theatres=theatres,
            staff=staff,
            queues=queues,
        )
