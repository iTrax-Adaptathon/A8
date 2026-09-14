from datetime import datetime, timezone
from sqlalchemy import (
    Column,
    Integer,
    String,
    DateTime,
    ForeignKey,
    Text,
)
from sqlalchemy.orm import relationship
from app.infrastructure.database.session import Base
from app.domain.entities import Department, Bed, Patient, FlowEvent
from app.domain.enums import PatientStatus, BedStatus, BedType, FlowEventType


def default_utc_now():
    return datetime.now(timezone.utc)


class DepartmentModel(Base):
    __tablename__ = "departments"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    name = Column(String, nullable=False, unique=True)
    code = Column(String, nullable=False, unique=True)
    created_at = Column(DateTime, nullable=False, default=default_utc_now)

    beds = relationship("BedModel", back_populates="department", cascade="all, delete-orphan")

    def to_entity(self, occupied_count: int = 0) -> Department:
        total_beds_count = len(self.beds) if self.beds else 0
        return Department(
            id=self.id,
            name=self.name,
            code=self.code,
            total_beds=total_beds_count,
            occupied_beds=occupied_count,
            created_at=self.created_at,
        )

    @classmethod
    def from_entity(cls, entity: Department) -> "DepartmentModel":
        return cls(
            id=entity.id,
            name=entity.name,
            code=entity.code,
            created_at=entity.created_at or default_utc_now(),
        )


class BedModel(Base):
    __tablename__ = "beds"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    bed_number = Column(String, nullable=False, unique=True)
    bed_type = Column(String, nullable=False, default=BedType.GENERAL.value)
    department_id = Column(Integer, ForeignKey("departments.id"), nullable=False, index=True)
    status = Column(String, nullable=False, default=BedStatus.AVAILABLE.value)
    current_patient_id = Column(Integer, ForeignKey("patients.id", ondelete="SET NULL"), nullable=True)
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
            created_at=entity.created_at or default_utc_now(),
        )


class PatientModel(Base):
    __tablename__ = "patients"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    name = Column(String, nullable=False)
    age = Column(Integer, nullable=False)
    gender = Column(String, nullable=False)
    medical_record_number = Column(String, nullable=False, unique=True)
    current_status = Column(String, nullable=False, default=PatientStatus.REGISTERED.value)
    current_department_id = Column(Integer, ForeignKey("departments.id", ondelete="SET NULL"), nullable=True)
    current_bed_id = Column(Integer, ForeignKey("beds.id", ondelete="SET NULL"), nullable=True)
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
    __tablename__ = "flow_events"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    event_type = Column(String, nullable=False, index=True)
    patient_id = Column(Integer, ForeignKey("patients.id"), nullable=False, index=True)
    from_department_id = Column(Integer, nullable=True)
    to_department_id = Column(Integer, nullable=True)
    from_bed_id = Column(Integer, nullable=True)
    to_bed_id = Column(Integer, nullable=True)
    timestamp = Column(DateTime, nullable=False, default=default_utc_now, index=True)
    notes = Column(Text, nullable=False, default="")

    def to_entity(self) -> FlowEvent:
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
        )
