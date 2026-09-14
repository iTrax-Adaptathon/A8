from typing import List, Optional
from app.infrastructure.repositories import PatientRepository
from app.domain.entities import Patient
from app.domain.enums import PatientStatus


class PatientService:
    def __init__(self, patient_repo: PatientRepository):
        self.patient_repo = patient_repo

    def create_patient(self, patient: Patient) -> Patient:
        return self.patient_repo.create(patient)

    def get_patient(self, patient_id: int) -> Optional[Patient]:
        return self.patient_repo.get_by_id(patient_id)

    def list_patients(
        self,
        status: Optional[PatientStatus] = None,
        department_id: Optional[int] = None,
    ) -> List[Patient]:
        return self.patient_repo.get_all(status=status, department_id=department_id)
