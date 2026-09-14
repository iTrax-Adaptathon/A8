from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional
from app.domain.enums import PatientStatus, BedStatus, BedType, FlowEventType


@dataclass
class Department:
    id: Optional[int]
    name: str
    code: str
    total_beds: int = 0
    occupied_beds: int = 0
    created_at: Optional[datetime] = None


@dataclass
class Bed:
    id: Optional[int]
    bed_number: str
    bed_type: BedType
    department_id: int
    status: BedStatus = BedStatus.AVAILABLE
    current_patient_id: Optional[int] = None
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
    id: Optional[int]
    event_type: FlowEventType
    patient_id: int
    timestamp: datetime
    from_department_id: Optional[int] = None
    to_department_id: Optional[int] = None
    from_bed_id: Optional[int] = None
    to_bed_id: Optional[int] = None
    notes: str = ""
