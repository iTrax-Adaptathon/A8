from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, Optional
from app.domain.enums import (
    PatientStatus,
    BedStatus,
    BedType,
    FlowEventType,
    TheatreStatus,
    TheatreSlotStatus,
    SurgeryStatus,
    StaffRole,
    StaffStatus,
    StaffAssignmentType,
    StaffAssignmentStatus,
    WaitlistResourceType,
    WaitlistStatus,
    ResourceType,
    EventSource,
)


@dataclass(frozen=True)
class Actor:
    """Who performed an operation. Never persisted on its own; copied onto
    FlowEvent rows (actor_id / actor_name). Populated from the X-Actor-ID and
    X-Actor-Name request headers, defaulting to the system actor."""

    id: str = "system"
    name: str = "System"


SYSTEM_ACTOR = Actor()


@dataclass
class Department:
    id: Optional[int]
    name: str
    code: str
    total_beds: int = 0
    occupied_beds: int = 0
    is_active: bool = True
    created_at: Optional[datetime] = None


@dataclass
class Bed:
    id: Optional[int]
    bed_number: str
    bed_type: BedType
    department_id: int
    status: BedStatus = BedStatus.AVAILABLE
    current_patient_id: Optional[int] = None
    is_active: bool = True
    created_at: Optional[datetime] = None


@dataclass
class Patient:
    id: Optional[int]
    name: str
    age: int
    gender: str
    medical_record_number: str
    current_status: PatientStatus = PatientStatus.REGISTERED
    current_department_id: Optional[int] = None
    current_bed_id: Optional[int] = None
    admitted_at: Optional[datetime] = None
    discharged_at: Optional[datetime] = None
    created_at: Optional[datetime] = None


@dataclass
class FlowEvent:
    """Immutable audit record. Every meaningful state change writes one."""

    id: Optional[int]
    event_type: FlowEventType
    timestamp: datetime
    patient_id: Optional[int] = None
    from_department_id: Optional[int] = None
    to_department_id: Optional[int] = None
    from_bed_id: Optional[int] = None
    to_bed_id: Optional[int] = None
    notes: str = ""
    resource_type: Optional[ResourceType] = None
    resource_id: Optional[int] = None
    department_id: Optional[int] = None
    previous_state: Optional[str] = None
    new_state: Optional[str] = None
    actor_id: str = "system"
    actor_name: str = "System"
    source: EventSource = EventSource.MANUAL
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class Theatre:
    id: Optional[int]
    name: str
    department_id: int
    status: TheatreStatus = TheatreStatus.AVAILABLE
    is_active: bool = True
    created_at: Optional[datetime] = None


@dataclass
class TheatreSlot:
    id: Optional[int]
    theatre_id: int
    start_time: datetime
    end_time: datetime
    status: TheatreSlotStatus = TheatreSlotStatus.AVAILABLE
    surgery_id: Optional[int] = None
    created_at: Optional[datetime] = None

    @property
    def duration_minutes(self) -> int:
        return int((self.end_time - self.start_time).total_seconds() // 60)


@dataclass
class Surgery:
    id: Optional[int]
    patient_id: int
    department_id: int
    procedure_name: str
    duration_minutes: int
    priority: int = 3  # 1 = most urgent ... 5 = elective
    status: SurgeryStatus = SurgeryStatus.WAITING
    theatre_id: Optional[int] = None
    slot_id: Optional[int] = None
    required_staff_role: Optional[StaffRole] = None
    created_at: Optional[datetime] = None
    scheduled_at: Optional[datetime] = None
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None


@dataclass
class Staff:
    id: Optional[int]
    name: str
    role: StaffRole
    department_id: int
    shift_start: datetime
    shift_end: datetime
    status: StaffStatus = StaffStatus.AVAILABLE
    is_active: bool = True
    created_at: Optional[datetime] = None


@dataclass
class StaffAssignment:
    id: Optional[int]
    staff_id: int
    assignment_type: StaffAssignmentType
    department_id: int
    start_time: datetime
    surgery_id: Optional[int] = None
    patient_id: Optional[int] = None
    end_time: Optional[datetime] = None
    status: StaffAssignmentStatus = StaffAssignmentStatus.ACTIVE
    released_at: Optional[datetime] = None


@dataclass
class WaitlistEntry:
    id: Optional[int]
    patient_id: int
    resource_type: WaitlistResourceType
    department_id: int
    priority: int  # 1 = most urgent ... 5 = lowest
    requested_at: datetime
    status: WaitlistStatus = WaitlistStatus.WAITING
    reason: str = ""
    surgery_id: Optional[int] = None
    required_bed_type: Optional[BedType] = None
    required_staff_role: Optional[StaffRole] = None
    fulfilled_at: Optional[datetime] = None
    fulfilled_resource_id: Optional[int] = None
