import json
from datetime import datetime, timezone
from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Column,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    text,
)
from sqlalchemy.orm import relationship
from app.infrastructure.database.session import Base
from app.domain.entities import (
    Department,
    Bed,
    Patient,
    FlowEvent,
    Theatre,
    TheatreSlot,
    Surgery,
    Staff,
    StaffAssignment,
    WaitlistEntry,
)
from app.domain.enums import (
    PatientStatus,
    BedStatus,
    BedType,
    FlowEventType,
    ResourceType,
    EventSource,
    TheatreStatus,
    TheatreSlotStatus,
    SurgeryStatus,
    StaffRole,
    StaffStatus,
    StaffAssignmentType,
    StaffAssignmentStatus,
    WaitlistResourceType,
    WaitlistStatus,
)


def default_utc_now():
    return datetime.now(timezone.utc)


def _enum_or_none(enum_cls, value):
    return enum_cls(value) if value is not None else None


def _value_or_none(value):
    return value.value if value is not None else None


class DepartmentModel(Base):
    __tablename__ = "departments"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    name = Column(String, nullable=False, unique=True)
    code = Column(String, nullable=False, unique=True)
    is_active = Column(Boolean, nullable=False, default=True, server_default=text("1"), index=True)
    created_at = Column(DateTime, nullable=False, default=default_utc_now)

    # No delete cascade: departments are deactivated, never destroyed, so that
    # beds and historical events keep resolving.
    beds = relationship("BedModel", back_populates="department")

    def to_entity(self, occupied_count: int = 0, total_beds: int = None) -> Department:
        if total_beds is None:
            total_beds = len([b for b in self.beds if b.is_active]) if self.beds else 0
        return Department(
            id=self.id,
            name=self.name,
            code=self.code,
            total_beds=total_beds,
            occupied_beds=occupied_count,
            is_active=bool(self.is_active),
            created_at=self.created_at,
        )

    @classmethod
    def from_entity(cls, entity: Department) -> "DepartmentModel":
        return cls(
            id=entity.id,
            name=entity.name,
            code=entity.code,
            is_active=entity.is_active,
            created_at=entity.created_at or default_utc_now(),
        )


class BedModel(Base):
    __tablename__ = "beds"
    __table_args__ = (
        # A bed is OCCUPIED exactly when it references a patient.
        CheckConstraint(
            "(status = 'OCCUPIED') = (current_patient_id IS NOT NULL)",
            name="ck_bed_occupied_has_patient",
        ),
        # One patient can never occupy two beds.
        Index(
            "ux_beds_current_patient",
            "current_patient_id",
            unique=True,
            sqlite_where=text("current_patient_id IS NOT NULL"),
        ),
        Index("ix_beds_department_status", "department_id", "status"),
    )

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    bed_number = Column(String, nullable=False, unique=True)
    bed_type = Column(String, nullable=False, default=BedType.GENERAL.value)
    department_id = Column(Integer, ForeignKey("departments.id"), nullable=False, index=True)
    status = Column(String, nullable=False, default=BedStatus.AVAILABLE.value)
    current_patient_id = Column(Integer, ForeignKey("patients.id"), nullable=True)
    is_active = Column(Boolean, nullable=False, default=True, server_default=text("1"), index=True)
    created_at = Column(DateTime, nullable=False, default=default_utc_now)

    department = relationship("DepartmentModel", back_populates="beds")

    def to_entity(self) -> Bed:
        return Bed(
            id=self.id,
            bed_number=self.bed_number,
            bed_type=BedType(self.bed_type),
            department_id=self.department_id,
            status=BedStatus(self.status),
            current_patient_id=self.current_patient_id,
            is_active=bool(self.is_active),
            created_at=self.created_at,
        )

    @classmethod
    def from_entity(cls, entity: Bed) -> "BedModel":
        return cls(
            id=entity.id,
            bed_number=entity.bed_number,
            bed_type=entity.bed_type.value,
            department_id=entity.department_id,
            status=entity.status.value,
            current_patient_id=entity.current_patient_id,
            is_active=entity.is_active,
            created_at=entity.created_at or default_utc_now(),
        )


class PatientModel(Base):
    __tablename__ = "patients"
    __table_args__ = (
        # One bed can never be the current bed of two patients.
        Index(
            "ux_patients_current_bed",
            "current_bed_id",
            unique=True,
            sqlite_where=text("current_bed_id IS NOT NULL"),
        ),
        Index("ix_patients_status", "current_status"),
    )

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    name = Column(String, nullable=False)
    age = Column(Integer, nullable=False)
    gender = Column(String, nullable=False)
    medical_record_number = Column(String, nullable=False, unique=True)
    current_status = Column(String, nullable=False, default=PatientStatus.REGISTERED.value)
    current_department_id = Column(Integer, ForeignKey("departments.id"), nullable=True)
    # use_alter breaks the beds <-> patients FK cycle for metadata sorting.
    current_bed_id = Column(
        Integer,
        ForeignKey("beds.id", use_alter=True, name="fk_patients_current_bed"),
        nullable=True,
    )
    admitted_at = Column(DateTime, nullable=True)
    discharged_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, nullable=False, default=default_utc_now)

    def to_entity(self) -> Patient:
        return Patient(
            id=self.id,
            name=self.name,
            age=self.age,
            gender=self.gender,
            medical_record_number=self.medical_record_number,
            current_status=PatientStatus(self.current_status),
            current_department_id=self.current_department_id,
            current_bed_id=self.current_bed_id,
            admitted_at=self.admitted_at,
            discharged_at=self.discharged_at,
            created_at=self.created_at,
        )

    @classmethod
    def from_entity(cls, entity: Patient) -> "PatientModel":
        return cls(
            id=entity.id,
            name=entity.name,
            age=entity.age,
            gender=entity.gender,
            medical_record_number=entity.medical_record_number,
            current_status=entity.current_status.value,
            current_department_id=entity.current_department_id,
            current_bed_id=entity.current_bed_id,
            admitted_at=entity.admitted_at,
            discharged_at=entity.discharged_at,
            created_at=entity.created_at or default_utc_now(),
        )


class FlowEventModel(Base):
    """Append-only audit log. Rows are never updated or deleted, and reference
    resources by plain integer id so they survive deactivation."""

    __tablename__ = "flow_events"
    __table_args__ = (
        Index("ix_flow_events_resource", "resource_type", "resource_id"),
        Index("ix_flow_events_patient_ts", "patient_id", "timestamp"),
    )

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    event_type = Column(String, nullable=False, index=True)
    patient_id = Column(Integer, ForeignKey("patients.id"), nullable=True, index=True)
    from_department_id = Column(Integer, nullable=True)
    to_department_id = Column(Integer, nullable=True)
    from_bed_id = Column(Integer, nullable=True)
    to_bed_id = Column(Integer, nullable=True)
    timestamp = Column(DateTime, nullable=False, default=default_utc_now, index=True)
    notes = Column(Text, nullable=False, default="")
    resource_type = Column(String, nullable=True)
    resource_id = Column(Integer, nullable=True)
    department_id = Column(Integer, nullable=True, index=True)
    previous_state = Column(String, nullable=True)
    new_state = Column(String, nullable=True)
    actor_id = Column(String, nullable=False, default="system")
    actor_name = Column(String, nullable=False, default="System")
    source = Column(String, nullable=False, default=EventSource.MANUAL.value)
    metadata_json = Column(Text, nullable=False, default="{}")

    def to_entity(self) -> FlowEvent:
        try:
            metadata = json.loads(self.metadata_json or "{}")
        except ValueError:
            metadata = {}
        return FlowEvent(
            id=self.id,
            event_type=FlowEventType(self.event_type),
            patient_id=self.patient_id,
            from_department_id=self.from_department_id,
            to_department_id=self.to_department_id,
            from_bed_id=self.from_bed_id,
            to_bed_id=self.to_bed_id,
            timestamp=self.timestamp,
            notes=self.notes,
            resource_type=_enum_or_none(ResourceType, self.resource_type),
            resource_id=self.resource_id,
            department_id=self.department_id,
            previous_state=self.previous_state,
            new_state=self.new_state,
            actor_id=self.actor_id,
            actor_name=self.actor_name,
            source=EventSource(self.source),
            metadata=metadata,
        )

    @classmethod
    def from_entity(cls, entity: FlowEvent) -> "FlowEventModel":
        return cls(
            id=entity.id,
            event_type=entity.event_type.value,
            patient_id=entity.patient_id,
            from_department_id=entity.from_department_id,
            to_department_id=entity.to_department_id,
            from_bed_id=entity.from_bed_id,
            to_bed_id=entity.to_bed_id,
            timestamp=entity.timestamp or default_utc_now(),
            notes=entity.notes or "",
            resource_type=_value_or_none(entity.resource_type),
            resource_id=entity.resource_id,
            department_id=entity.department_id,
            previous_state=entity.previous_state,
            new_state=entity.new_state,
            actor_id=entity.actor_id,
            actor_name=entity.actor_name,
            source=entity.source.value,
            metadata_json=json.dumps(entity.metadata or {}, default=str, sort_keys=True),
        )


class TheatreModel(Base):
    __tablename__ = "theatres"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    name = Column(String, nullable=False, unique=True)
    department_id = Column(Integer, ForeignKey("departments.id"), nullable=False, index=True)
    status = Column(String, nullable=False, default=TheatreStatus.AVAILABLE.value, index=True)
    is_active = Column(Boolean, nullable=False, default=True, server_default=text("1"), index=True)
    created_at = Column(DateTime, nullable=False, default=default_utc_now)

    def to_entity(self) -> Theatre:
        return Theatre(
            id=self.id,
            name=self.name,
            department_id=self.department_id,
            status=TheatreStatus(self.status),
            is_active=bool(self.is_active),
            created_at=self.created_at,
        )

    @classmethod
    def from_entity(cls, entity: Theatre) -> "TheatreModel":
        return cls(
            id=entity.id,
            name=entity.name,
            department_id=entity.department_id,
            status=entity.status.value,
            is_active=entity.is_active,
            created_at=entity.created_at or default_utc_now(),
        )


class TheatreSlotModel(Base):
    __tablename__ = "theatre_slots"
    __table_args__ = (
        CheckConstraint("end_time > start_time", name="ck_slot_end_after_start"),
        # A slot is BOOKED exactly when it references a surgery.
        CheckConstraint(
            "(status IN ('BOOKED', 'COMPLETED') AND surgery_id IS NOT NULL) OR "
            "(status IN ('AVAILABLE', 'CANCELLED') AND surgery_id IS NULL)",
            name="ck_slot_booked_has_surgery",
        ),
        # One surgery can never hold two live slots.
        Index(
            "ux_theatre_slots_surgery",
            "surgery_id",
            unique=True,
            sqlite_where=text("surgery_id IS NOT NULL AND status = 'BOOKED'"),
        ),
        Index("ix_theatre_slots_theatre_start", "theatre_id", "start_time"),
        Index("ix_theatre_slots_status", "status"),
    )

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    theatre_id = Column(Integer, ForeignKey("theatres.id"), nullable=False)
    start_time = Column(DateTime, nullable=False)
    end_time = Column(DateTime, nullable=False)
    status = Column(String, nullable=False, default=TheatreSlotStatus.AVAILABLE.value)
    surgery_id = Column(Integer, ForeignKey("surgeries.id", use_alter=True, name="fk_slots_surgery"), nullable=True)
    created_at = Column(DateTime, nullable=False, default=default_utc_now)

    def to_entity(self) -> TheatreSlot:
        return TheatreSlot(
            id=self.id,
            theatre_id=self.theatre_id,
            start_time=self.start_time,
            end_time=self.end_time,
            status=TheatreSlotStatus(self.status),
            surgery_id=self.surgery_id,
            created_at=self.created_at,
        )

    @classmethod
    def from_entity(cls, entity: TheatreSlot) -> "TheatreSlotModel":
        return cls(
            id=entity.id,
            theatre_id=entity.theatre_id,
            start_time=entity.start_time,
            end_time=entity.end_time,
            status=entity.status.value,
            surgery_id=entity.surgery_id,
            created_at=entity.created_at or default_utc_now(),
        )


class SurgeryModel(Base):
    __tablename__ = "surgeries"
    __table_args__ = (
        CheckConstraint("duration_minutes >= 15 AND duration_minutes <= 1440", name="ck_surgery_duration"),
        CheckConstraint("priority >= 1 AND priority <= 5", name="ck_surgery_priority"),
        Index("ix_surgeries_status_priority", "status", "priority"),
        Index("ix_surgeries_patient", "patient_id"),
    )

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    patient_id = Column(Integer, ForeignKey("patients.id"), nullable=False)
    department_id = Column(Integer, ForeignKey("departments.id"), nullable=False, index=True)
    procedure_name = Column(String, nullable=False)
    duration_minutes = Column(Integer, nullable=False)
    priority = Column(Integer, nullable=False, default=3)
    status = Column(String, nullable=False, default=SurgeryStatus.WAITING.value)
    theatre_id = Column(Integer, ForeignKey("theatres.id"), nullable=True)
    slot_id = Column(Integer, ForeignKey("theatre_slots.id"), nullable=True)
    required_staff_role = Column(String, nullable=True)
    created_at = Column(DateTime, nullable=False, default=default_utc_now)
    scheduled_at = Column(DateTime, nullable=True)
    started_at = Column(DateTime, nullable=True)
    completed_at = Column(DateTime, nullable=True)

    def to_entity(self) -> Surgery:
        return Surgery(
            id=self.id,
            patient_id=self.patient_id,
            department_id=self.department_id,
            procedure_name=self.procedure_name,
            duration_minutes=self.duration_minutes,
            priority=self.priority,
            status=SurgeryStatus(self.status),
            theatre_id=self.theatre_id,
            slot_id=self.slot_id,
            required_staff_role=_enum_or_none(StaffRole, self.required_staff_role),
            created_at=self.created_at,
            scheduled_at=self.scheduled_at,
            started_at=self.started_at,
            completed_at=self.completed_at,
        )

    @classmethod
    def from_entity(cls, entity: Surgery) -> "SurgeryModel":
        return cls(
            id=entity.id,
            patient_id=entity.patient_id,
            department_id=entity.department_id,
            procedure_name=entity.procedure_name,
            duration_minutes=entity.duration_minutes,
            priority=entity.priority,
            status=entity.status.value,
            theatre_id=entity.theatre_id,
            slot_id=entity.slot_id,
            required_staff_role=_value_or_none(entity.required_staff_role),
            created_at=entity.created_at or default_utc_now(),
            scheduled_at=entity.scheduled_at,
            started_at=entity.started_at,
            completed_at=entity.completed_at,
        )


class StaffModel(Base):
    __tablename__ = "staff"
    __table_args__ = (
        CheckConstraint("shift_end > shift_start", name="ck_staff_shift"),
        Index("ix_staff_department_role_status", "department_id", "role", "status"),
    )

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    name = Column(String, nullable=False)
    role = Column(String, nullable=False)
    department_id = Column(Integer, ForeignKey("departments.id"), nullable=False)
    shift_start = Column(DateTime, nullable=False)
    shift_end = Column(DateTime, nullable=False)
    status = Column(String, nullable=False, default=StaffStatus.AVAILABLE.value)
    is_active = Column(Boolean, nullable=False, default=True, server_default=text("1"), index=True)
    created_at = Column(DateTime, nullable=False, default=default_utc_now)

    def to_entity(self) -> Staff:
        return Staff(
            id=self.id,
            name=self.name,
            role=StaffRole(self.role),
            department_id=self.department_id,
            shift_start=self.shift_start,
            shift_end=self.shift_end,
            status=StaffStatus(self.status),
            is_active=bool(self.is_active),
            created_at=self.created_at,
        )

    @classmethod
    def from_entity(cls, entity: Staff) -> "StaffModel":
        return cls(
            id=entity.id,
            name=entity.name,
            role=entity.role.value,
            department_id=entity.department_id,
            shift_start=entity.shift_start,
            shift_end=entity.shift_end,
            status=entity.status.value,
            is_active=entity.is_active,
            created_at=entity.created_at or default_utc_now(),
        )


class StaffAssignmentModel(Base):
    __tablename__ = "staff_assignments"
    __table_args__ = (
        # A staff member holds at most one ACTIVE assignment.
        Index(
            "ux_staff_assignments_active_staff",
            "staff_id",
            unique=True,
            sqlite_where=text("status = 'ACTIVE'"),
        ),
        CheckConstraint(
            "(assignment_type = 'SURGERY' AND surgery_id IS NOT NULL) OR "
            "(assignment_type = 'PATIENT' AND patient_id IS NOT NULL)",
            name="ck_staff_assignment_target",
        ),
        Index("ix_staff_assignments_surgery", "surgery_id"),
        Index("ix_staff_assignments_patient", "patient_id"),
    )

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    staff_id = Column(Integer, ForeignKey("staff.id"), nullable=False)
    assignment_type = Column(String, nullable=False)
    surgery_id = Column(Integer, ForeignKey("surgeries.id"), nullable=True)
    patient_id = Column(Integer, ForeignKey("patients.id"), nullable=True)
    department_id = Column(Integer, ForeignKey("departments.id"), nullable=False)
    start_time = Column(DateTime, nullable=False)
    end_time = Column(DateTime, nullable=True)
    status = Column(String, nullable=False, default=StaffAssignmentStatus.ACTIVE.value)
    released_at = Column(DateTime, nullable=True)

    def to_entity(self) -> StaffAssignment:
        return StaffAssignment(
            id=self.id,
            staff_id=self.staff_id,
            assignment_type=StaffAssignmentType(self.assignment_type),
            surgery_id=self.surgery_id,
            patient_id=self.patient_id,
            department_id=self.department_id,
            start_time=self.start_time,
            end_time=self.end_time,
            status=StaffAssignmentStatus(self.status),
            released_at=self.released_at,
        )

    @classmethod
    def from_entity(cls, entity: StaffAssignment) -> "StaffAssignmentModel":
        return cls(
            id=entity.id,
            staff_id=entity.staff_id,
            assignment_type=entity.assignment_type.value,
            surgery_id=entity.surgery_id,
            patient_id=entity.patient_id,
            department_id=entity.department_id,
            start_time=entity.start_time,
            end_time=entity.end_time,
            status=entity.status.value,
            released_at=entity.released_at,
        )


class WaitlistEntryModel(Base):
    __tablename__ = "waitlist_entries"
    __table_args__ = (
        CheckConstraint("priority >= 1 AND priority <= 5", name="ck_waitlist_priority"),
        Index("ix_waitlist_queue", "resource_type", "status", "priority", "requested_at"),
        Index("ix_waitlist_patient", "patient_id"),
    )

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    patient_id = Column(Integer, ForeignKey("patients.id"), nullable=False)
    resource_type = Column(String, nullable=False)
    department_id = Column(Integer, ForeignKey("departments.id"), nullable=False)
    priority = Column(Integer, nullable=False, default=3)
    requested_at = Column(DateTime, nullable=False, default=default_utc_now)
    status = Column(String, nullable=False, default=WaitlistStatus.WAITING.value)
    reason = Column(Text, nullable=False, default="")
    surgery_id = Column(Integer, ForeignKey("surgeries.id"), nullable=True)
    required_bed_type = Column(String, nullable=True)
    required_staff_role = Column(String, nullable=True)
    fulfilled_at = Column(DateTime, nullable=True)
    fulfilled_resource_id = Column(Integer, nullable=True)

    def to_entity(self) -> WaitlistEntry:
        return WaitlistEntry(
            id=self.id,
            patient_id=self.patient_id,
            resource_type=WaitlistResourceType(self.resource_type),
            department_id=self.department_id,
            priority=self.priority,
            requested_at=self.requested_at,
            status=WaitlistStatus(self.status),
            reason=self.reason or "",
            surgery_id=self.surgery_id,
            required_bed_type=_enum_or_none(BedType, self.required_bed_type),
            required_staff_role=_enum_or_none(StaffRole, self.required_staff_role),
            fulfilled_at=self.fulfilled_at,
            fulfilled_resource_id=self.fulfilled_resource_id,
        )

    @classmethod
    def from_entity(cls, entity: WaitlistEntry) -> "WaitlistEntryModel":
        return cls(
            id=entity.id,
            patient_id=entity.patient_id,
            resource_type=entity.resource_type.value,
            department_id=entity.department_id,
            priority=entity.priority,
            requested_at=entity.requested_at or default_utc_now(),
            status=entity.status.value,
            reason=entity.reason or "",
            surgery_id=entity.surgery_id,
            required_bed_type=_value_or_none(entity.required_bed_type),
            required_staff_role=_value_or_none(entity.required_staff_role),
            fulfilled_at=entity.fulfilled_at,
            fulfilled_resource_id=entity.fulfilled_resource_id,
        )
