from app.domain.enums import PatientStatus, BedStatus, CapacityAlertLevel
from app.core.config import settings


class DomainValidationError(Exception):
    pass


class InvalidStateTransitionError(DomainValidationError):
    pass


class BedAssignmentError(DomainValidationError):
    pass


class PatientPolicy:
    """Validates Patient lifecycle state transitions."""

    _ALLOWED_TRANSITIONS = {
        PatientStatus.REGISTERED: {PatientStatus.ADMITTED},
        PatientStatus.ADMITTED: {PatientStatus.TRANSFERRED, PatientStatus.DISCHARGED},
        PatientStatus.TRANSFERRED: {PatientStatus.TRANSFERRED, PatientStatus.DISCHARGED},
        PatientStatus.DISCHARGED: set(),  # Terminal
    }

    @classmethod
    def validate_transition(cls, current_status: PatientStatus, new_status: PatientStatus) -> None:
        if current_status == new_status:
            return
        allowed = cls._ALLOWED_TRANSITIONS.get(current_status, set())
        if new_status not in allowed:
            raise InvalidStateTransitionError(
                f"Cannot transition patient from '{current_status.value}' to '{new_status.value}'"
            )


class BedPolicy:
    """Validates Bed assignments and state updates."""

    @classmethod
    def validate_assignment(cls, bed_status: BedStatus) -> None:
        if bed_status != BedStatus.AVAILABLE:
            raise BedAssignmentError(f"Bed is currently in status '{bed_status.value}' and cannot be assigned.")


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
