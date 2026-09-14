from app.infrastructure.repositories.patient_repository import PatientRepository
from app.infrastructure.repositories.bed_repository import BedRepository
from app.infrastructure.repositories.department_repository import DepartmentRepository
from app.infrastructure.repositories.flow_event_repository import FlowEventRepository

__all__ = [
    "PatientRepository",
    "BedRepository",
    "DepartmentRepository",
    "FlowEventRepository",
]
