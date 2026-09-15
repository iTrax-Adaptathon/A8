"""Deterministic business rules.

Every rule in this module is an explicit, predefined check. There is no
statistical, learned or AI-based decision-making anywhere in FlowCare.
"""
from datetime import datetime, timedelta, timezone
from typing import Dict, Iterable, Optional, Set, Tuple

from app.core.config import settings
from app.domain.entities import (
    Bed,
    Patient,
    Staff,
    Surgery,
    Theatre,
    TheatreSlot,
    WaitlistEntry,
)
from app.domain.enums import (
    BedStatus,
    CapacityAlertLevel,
    PatientStatus,
    StaffAssignmentType,
    StaffRole,
    StaffStatus,
    SurgeryStatus,
    TheatreSlotStatus,
    TheatreStatus,
)


# ---------------------------------------------------------------------------
# Errors (mapped to HTTP codes in app/core/exception_handlers.py)
# ---------------------------------------------------------------------------
class DomainValidationError(Exception):
    """Invalid input / business validation failure -> 422."""


class NotFoundError(DomainValidationError):
    """Referenced entity does not exist -> 404."""


class ConflictError(DomainValidationError):
    """Current state does not allow the operation (state conflict, double
    booking, lost concurrent claim) -> 409."""


class InvalidStateTransitionError(ConflictError):
    pass


class BedAssignmentError(ConflictError):
    pass


# ---------------------------------------------------------------------------
# Generic transition-table helper
# ---------------------------------------------------------------------------
def _validate_transition(kind: str, table: Dict, current, new) -> None:
    if current == new:
        raise InvalidStateTransitionError(f"{kind} is already in status '{current.value}'")
    allowed: Set = table.get(current, set())
    if new not in allowed:
        raise InvalidStateTransitionError(
            f"Cannot transition {kind} from '{current.value}' to '{new.value}'"
        )


def _as_utc(value: datetime) -> datetime:
    """SQLite stores naive datetimes; compare everything as naive UTC."""
    if value.tzinfo is not None:
        return value.astimezone(timezone.utc).replace(tzinfo=None)
    return value


def utc_now() -> datetime:
    """Naive UTC timestamp (SQLite has no timezone support; the API serialises
    every datetime as UTC with a trailing Z)."""
    return datetime.now(timezone.utc).replace(tzinfo=None)


def to_naive_utc(value: Optional[datetime]) -> Optional[datetime]:
    if value is None:
        return None
    return _as_utc(value)


# ---------------------------------------------------------------------------
# Patients
# ---------------------------------------------------------------------------
class PatientPolicy:
    """Validates Patient lifecycle state transitions."""

    _ALLOWED_TRANSITIONS = {
        PatientStatus.REGISTERED: {PatientStatus.ADMITTED},
        PatientStatus.ADMITTED: {PatientStatus.TRANSFERRED, PatientStatus.DISCHARGED},
        PatientStatus.TRANSFERRED: {PatientStatus.TRANSFERRED, PatientStatus.DISCHARGED},
        PatientStatus.DISCHARGED: set(),  # Terminal
    }

    IN_BED_STATUSES = {PatientStatus.ADMITTED, PatientStatus.TRANSFERRED}

    @classmethod
    def validate_transition(cls, current_status: PatientStatus, new_status: PatientStatus) -> None:
        if current_status == new_status:
            return
        allowed = cls._ALLOWED_TRANSITIONS.get(current_status, set())
        if new_status not in allowed:
            raise InvalidStateTransitionError(
                f"Cannot transition patient from '{current_status.value}' to '{new_status.value}'"
            )

    @classmethod
    def validate_admittable(cls, patient: Patient) -> None:
        if patient.current_status != PatientStatus.REGISTERED:
            raise InvalidStateTransitionError(
                f"Patient {patient.id} cannot be admitted from status '{patient.current_status.value}'"
            )
        if patient.current_bed_id is not None:
            raise ConflictError(f"Patient {patient.id} already occupies bed {patient.current_bed_id}")

    @classmethod
    def validate_transferable(cls, patient: Patient) -> None:
        if patient.current_status not in cls.IN_BED_STATUSES:
            raise InvalidStateTransitionError(
                f"Patient {patient.id} is not currently admitted (status: {patient.current_status.value})"
            )

    @classmethod
    def validate_dischargeable(cls, patient: Patient) -> None:
        if patient.current_status not in cls.IN_BED_STATUSES:
            raise InvalidStateTransitionError(
                f"Patient {patient.id} cannot be discharged from status {patient.current_status.value}"
            )

    @classmethod
    def validate_active(cls, patient: Patient) -> None:
        if patient.current_status == PatientStatus.DISCHARGED:
            raise ConflictError(f"Patient {patient.id} is discharged")


# ---------------------------------------------------------------------------
# Beds
# ---------------------------------------------------------------------------
class BedPolicy:
    """Validates Bed assignments and status updates.

    Manual status changes (PATCH /beds/{id}/status) may only move between the
    non-occupied states. OCCUPIED is entered only through admission/transfer
    and left only through the transfer/discharge release workflow
    (OCCUPIED -> CLEANING), after which POST /beds/{id}/release makes the bed
    AVAILABLE again.
    """

    _MANUAL_TRANSITIONS = {
        BedStatus.AVAILABLE: {BedStatus.CLEANING, BedStatus.MAINTENANCE},
        BedStatus.CLEANING: {BedStatus.AVAILABLE, BedStatus.MAINTENANCE},
        BedStatus.MAINTENANCE: {BedStatus.AVAILABLE, BedStatus.CLEANING},
        BedStatus.OCCUPIED: set(),
    }

    @classmethod
    def validate_assignment(cls, bed_status: BedStatus, is_active: bool = True, current_patient_id: Optional[int] = None) -> None:
        if not is_active:
            raise BedAssignmentError("Bed is inactive and cannot be assigned.")
        if bed_status != BedStatus.AVAILABLE:
            raise BedAssignmentError(f"Bed is currently in status '{bed_status.value}' and cannot be assigned.")
        if current_patient_id is not None:
            raise BedAssignmentError(f"Bed is already assigned to patient {current_patient_id}.")

    @classmethod
    def validate_status_transition(cls, current: BedStatus, new: BedStatus) -> None:
        if current == BedStatus.OCCUPIED:
            raise InvalidStateTransitionError(
                "An OCCUPIED bed cannot change status directly; discharge or transfer the patient first."
            )
        if new == BedStatus.OCCUPIED:
            raise InvalidStateTransitionError(
                "A bed can only become OCCUPIED through patient admission or transfer."
            )
        _validate_transition("bed", cls._MANUAL_TRANSITIONS, current, new)

    @classmethod
    def validate_release(cls, current: BedStatus) -> None:
        """Release workflow: CLEANING -> AVAILABLE only."""
        if current != BedStatus.CLEANING:
            raise InvalidStateTransitionError(
                f"Only a CLEANING bed can be released to AVAILABLE (current: '{current.value}')"
            )

    @classmethod
    def validate_deactivation(cls, bed: Bed) -> None:
        if bed.status == BedStatus.OCCUPIED or bed.current_patient_id is not None:
            raise ConflictError(f"Bed {bed.id} is occupied and cannot be deactivated")


# ---------------------------------------------------------------------------
# Theatres and slots (statuses are independent of each other)
# ---------------------------------------------------------------------------
class TheatrePolicy:
    _MANUAL_TRANSITIONS = {
        TheatreStatus.AVAILABLE: {TheatreStatus.UNAVAILABLE, TheatreStatus.CLEANING},
        TheatreStatus.CLEANING: {TheatreStatus.AVAILABLE, TheatreStatus.UNAVAILABLE},
        TheatreStatus.UNAVAILABLE: {TheatreStatus.AVAILABLE},
        TheatreStatus.IN_USE: set(),
    }

    @classmethod
    def validate_status_transition(cls, current: TheatreStatus, new: TheatreStatus) -> None:
        if current == TheatreStatus.IN_USE:
            raise InvalidStateTransitionError("A theatre IN_USE can only change status when its surgery completes.")
        if new == TheatreStatus.IN_USE:
            raise InvalidStateTransitionError("A theatre becomes IN_USE only when a surgery starts.")
        _validate_transition("theatre", cls._MANUAL_TRANSITIONS, current, new)

    @classmethod
    def validate_release(cls, current: TheatreStatus) -> None:
        if current != TheatreStatus.CLEANING:
            raise InvalidStateTransitionError(
                f"Only a CLEANING theatre can be released to AVAILABLE (current: '{current.value}')"
            )

    @classmethod
    def validate_bookable(cls, theatre: Theatre) -> None:
        if not theatre.is_active:
            raise ConflictError(f"Theatre {theatre.id} is inactive")
        if theatre.status != TheatreStatus.AVAILABLE:
            raise ConflictError(f"Theatre {theatre.id} is '{theatre.status.value}' and cannot be booked")

    @classmethod
    def validate_deactivation(cls, theatre: Theatre, booked_slot_count: int) -> None:
        if theatre.status == TheatreStatus.IN_USE:
            raise ConflictError(f"Theatre {theatre.id} is in use and cannot be deactivated")
        if booked_slot_count > 0:
            raise ConflictError(f"Theatre {theatre.id} has {booked_slot_count} booked slot(s) and cannot be deactivated")


class TheatreSlotPolicy:
    MIN_DURATION = timedelta(minutes=15)
    MAX_DURATION = timedelta(hours=24)

    @classmethod
    def validate_window(cls, start_time: datetime, end_time: datetime) -> None:
        if end_time <= start_time:
            raise DomainValidationError("Slot endTime must be after startTime")
        duration = end_time - start_time
        if duration < cls.MIN_DURATION:
            raise DomainValidationError("Slot must be at least 15 minutes long")
        if duration > cls.MAX_DURATION:
            raise DomainValidationError("Slot must not exceed 24 hours")

    @classmethod
    def overlaps(cls, a_start: datetime, a_end: datetime, b_start: datetime, b_end: datetime) -> bool:
        return _as_utc(a_start) < _as_utc(b_end) and _as_utc(b_start) < _as_utc(a_end)

    @classmethod
    def validate_no_overlap(cls, start_time: datetime, end_time: datetime, existing: Iterable[TheatreSlot]) -> None:
        for slot in existing:
            if slot.status == TheatreSlotStatus.CANCELLED:
                continue
            if cls.overlaps(start_time, end_time, slot.start_time, slot.end_time):
                raise ConflictError(
                    f"Slot overlaps existing slot {slot.id} ({slot.start_time.isoformat()} - {slot.end_time.isoformat()})"
                )

    @classmethod
    def validate_bookable(cls, slot: TheatreSlot) -> None:
        if slot.status != TheatreSlotStatus.AVAILABLE:
            raise ConflictError(f"Theatre slot {slot.id} is '{slot.status.value}' and cannot be booked")
        if slot.surgery_id is not None:
            raise ConflictError(f"Theatre slot {slot.id} is already booked by surgery {slot.surgery_id}")

    @classmethod
    def validate_fits(cls, slot: TheatreSlot, duration_minutes: int) -> None:
        if slot.duration_minutes < duration_minutes:
            raise ConflictError(
                f"Surgery duration {duration_minutes} min exceeds slot {slot.id} length {slot.duration_minutes} min"
            )

    @classmethod
    def validate_cancellable(cls, slot: TheatreSlot) -> None:
        if slot.status != TheatreSlotStatus.AVAILABLE:
            raise InvalidStateTransitionError(
                f"Only an AVAILABLE slot can be cancelled (slot {slot.id} is '{slot.status.value}')"
            )


# ---------------------------------------------------------------------------
# Surgeries
# ---------------------------------------------------------------------------
class SurgeryPolicy:
    MIN_DURATION_MINUTES = 15
    MAX_DURATION_MINUTES = 1440
    MIN_PRIORITY = 1
    MAX_PRIORITY = 5

    _TRANSITIONS = {
        SurgeryStatus.WAITING: {SurgeryStatus.SCHEDULED, SurgeryStatus.CANCELLED},
        SurgeryStatus.SCHEDULED: {SurgeryStatus.IN_PROGRESS, SurgeryStatus.WAITING, SurgeryStatus.CANCELLED},
        SurgeryStatus.IN_PROGRESS: {SurgeryStatus.COMPLETED},
        SurgeryStatus.COMPLETED: set(),
        SurgeryStatus.CANCELLED: set(),
    }

    @classmethod
    def validate_transition(cls, current: SurgeryStatus, new: SurgeryStatus) -> None:
        _validate_transition("surgery", cls._TRANSITIONS, current, new)

    @classmethod
    def validate_definition(cls, duration_minutes: int, priority: int) -> None:
        if not cls.MIN_DURATION_MINUTES <= duration_minutes <= cls.MAX_DURATION_MINUTES:
            raise DomainValidationError(
                f"durationMinutes must be between {cls.MIN_DURATION_MINUTES} and {cls.MAX_DURATION_MINUTES}"
            )
        if not cls.MIN_PRIORITY <= priority <= cls.MAX_PRIORITY:
            raise DomainValidationError(f"priority must be between {cls.MIN_PRIORITY} and {cls.MAX_PRIORITY}")

    @classmethod
    def validate_schedulable(cls, surgery: Surgery, patient: Patient, theatre: Theatre, slot: TheatreSlot) -> None:
        cls.validate_transition(surgery.status, SurgeryStatus.SCHEDULED)
        if surgery.slot_id is not None:
            raise ConflictError(f"Surgery {surgery.id} already holds theatre slot {surgery.slot_id}")
        PatientPolicy.validate_active(patient)
        TheatrePolicy.validate_bookable(theatre)
        if slot.theatre_id != theatre.id:
            raise DomainValidationError(f"Slot {slot.id} does not belong to theatre {theatre.id}")
        if theatre.department_id != surgery.department_id:
            raise ConflictError(
                f"Theatre {theatre.id} belongs to department {theatre.department_id}, "
                f"surgery requires department {surgery.department_id}"
            )
        TheatreSlotPolicy.validate_bookable(slot)
        TheatreSlotPolicy.validate_fits(slot, surgery.duration_minutes)


# ---------------------------------------------------------------------------
# Staff
# ---------------------------------------------------------------------------
class StaffPolicy:
    _MANUAL_TRANSITIONS = {
        StaffStatus.OFF_DUTY: {StaffStatus.AVAILABLE},
        StaffStatus.AVAILABLE: {StaffStatus.OFF_DUTY},
        StaffStatus.ASSIGNED: set(),
    }

    @classmethod
    def validate_status_transition(cls, current: StaffStatus, new: StaffStatus) -> None:
        if current == StaffStatus.ASSIGNED:
            raise InvalidStateTransitionError("ASSIGNED staff must be released before changing status.")
        if new == StaffStatus.ASSIGNED:
            raise InvalidStateTransitionError("Staff become ASSIGNED only through an assignment.")
        _validate_transition("staff", cls._MANUAL_TRANSITIONS, current, new)

    @classmethod
    def shift_covers(cls, staff: Staff, start: datetime, end: Optional[datetime]) -> bool:
        s, e = _as_utc(staff.shift_start), _as_utc(staff.shift_end)
        if _as_utc(start) < s or _as_utc(start) > e:
            return False
        if end is not None and _as_utc(end) > e:
            return False
        return True

    @classmethod
    def validate_assignment(
        cls,
        staff: Staff,
        required_role: Optional[StaffRole],
        department_id: int,
        window_start: datetime,
        window_end: Optional[datetime],
        has_active_assignment: bool,
    ) -> None:
        if not staff.is_active:
            raise ConflictError(f"Staff {staff.id} is inactive")
        if staff.status != StaffStatus.AVAILABLE:
            raise ConflictError(f"Staff {staff.id} is '{staff.status.value}' and cannot be assigned")
        if has_active_assignment:
            raise ConflictError(f"Staff {staff.id} already has an active assignment")
        if required_role is not None and staff.role != required_role:
            raise ConflictError(
                f"Staff {staff.id} has role {staff.role.value}; assignment requires {required_role.value}"
            )
        if staff.department_id != department_id:
            raise ConflictError(
                f"Staff {staff.id} belongs to department {staff.department_id}, assignment requires department {department_id}"
            )
        if not cls.shift_covers(staff, window_start, window_end):
            raise ConflictError(f"Assignment window falls outside the shift of staff {staff.id}")

    @classmethod
    def validate_deactivation(cls, staff: Staff) -> None:
        if staff.status == StaffStatus.ASSIGNED:
            raise ConflictError(f"Staff {staff.id} is assigned and cannot be deactivated")


# ---------------------------------------------------------------------------
# Waitlist queue rule
# ---------------------------------------------------------------------------
class WaitlistPolicy:
    """Deterministic queue ordering.

    1. priority ascending (1 = most urgent)
    2. requested_at ascending (longest waiting first)
    3. id ascending (final tie-break so the order is total)
    """

    MIN_PRIORITY = 1
    MAX_PRIORITY = 5

    @classmethod
    def queue_sort_key(cls, entry: WaitlistEntry) -> Tuple[int, datetime, int]:
        return (entry.priority, _as_utc(entry.requested_at), entry.id or 0)

    @classmethod
    def validate_priority(cls, priority: int) -> None:
        if not cls.MIN_PRIORITY <= priority <= cls.MAX_PRIORITY:
            raise DomainValidationError(f"priority must be between {cls.MIN_PRIORITY} and {cls.MAX_PRIORITY}")


# ---------------------------------------------------------------------------
# Matching eligibility (pure predicates; return a rejection reason or None)
# ---------------------------------------------------------------------------
class MatchingPolicy:
    @classmethod
    def bed_ineligibility(cls, bed: Bed, entry: WaitlistEntry, patient: Patient) -> Optional[str]:
        if not bed.is_active or bed.status != BedStatus.AVAILABLE or bed.current_patient_id is not None:
            return "bed is not assignable"
        if bed.department_id != entry.department_id:
            return "department mismatch"
        if entry.required_bed_type is not None and bed.bed_type != entry.required_bed_type:
            return f"requires {entry.required_bed_type.value} bed"
        if patient.current_status == PatientStatus.DISCHARGED:
            return "patient discharged"
        if patient.current_status == PatientStatus.REGISTERED and patient.current_bed_id is not None:
            return "patient already has a bed"
        if patient.current_status in PatientPolicy.IN_BED_STATUSES and patient.current_bed_id == bed.id:
            return "patient already in this bed"
        return None

    @classmethod
    def slot_ineligibility(cls, slot: TheatreSlot, theatre: Theatre, surgery: Surgery, patient: Patient, now: datetime) -> Optional[str]:
        if slot.status != TheatreSlotStatus.AVAILABLE or slot.surgery_id is not None:
            return "slot is not available"
        if not theatre.is_active or theatre.status != TheatreStatus.AVAILABLE:
            return "theatre is not available"
        if theatre.department_id != surgery.department_id:
            return "department mismatch"
        if surgery.status != SurgeryStatus.WAITING or surgery.slot_id is not None:
            return "surgery is not waiting"
        if slot.duration_minutes < surgery.duration_minutes:
            return "slot too short"
        if _as_utc(slot.start_time) < _as_utc(now):
            return "slot already started"
        if patient.current_status == PatientStatus.DISCHARGED:
            return "patient discharged"
        return None

    @classmethod
    def staff_ineligibility(
        cls,
        staff: Staff,
        entry: WaitlistEntry,
        has_active_assignment: bool,
        window_start: datetime,
        window_end: Optional[datetime],
    ) -> Optional[str]:
        if not staff.is_active or staff.status != StaffStatus.AVAILABLE or has_active_assignment:
            return "staff is not available"
        if entry.required_staff_role is not None and staff.role != entry.required_staff_role:
            return f"requires {entry.required_staff_role.value}"
        if staff.department_id != entry.department_id:
            return "department mismatch"
        if not StaffPolicy.shift_covers(staff, window_start, window_end):
            return "outside shift"
        return None


# ---------------------------------------------------------------------------
# Capacity
# ---------------------------------------------------------------------------
class CapacityPolicy:
    """Calculates utilization and alert thresholds."""

    @classmethod
    def calculate_utilization_percentage(cls, total_beds: int, occupied_beds: int) -> float:
        if total_beds <= 0:
            return 0.0
        return round((occupied_beds / total_beds) * 100.0, 1)

    @classmethod
    def evaluate_alert_level(cls, occupancy_percentage: float) -> CapacityAlertLevel:
        if occupancy_percentage >= settings.CRITICAL_UTILIZATION_THRESHOLD:
            return CapacityAlertLevel.CRITICAL_CAPACITY
        elif occupancy_percentage >= settings.HIGH_UTILIZATION_THRESHOLD:
            return CapacityAlertLevel.HIGH_UTILIZATION
        return CapacityAlertLevel.NORMAL
