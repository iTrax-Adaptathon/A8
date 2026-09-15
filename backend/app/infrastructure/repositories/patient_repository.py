from datetime import datetime
from typing import List, Optional
from sqlalchemy import update
from sqlalchemy.orm import Session
from app.infrastructure.database.models import PatientModel
from app.infrastructure.repositories.base import BaseRepository
from app.domain.entities import Patient
from app.domain.enums import PatientStatus


class PatientRepository(BaseRepository):
    def __init__(self, db: Session):
        super().__init__(db)

    def get_by_id(self, patient_id: int) -> Optional[Patient]:
        model = self.db.get(PatientModel, patient_id)
        return model.to_entity() if model else None

    def _base_query(self, status: Optional[PatientStatus] = None, department_id: Optional[int] = None):
        query = self.db.query(PatientModel)
        if status:
            query = query.filter(PatientModel.current_status == status.value)
        if department_id:
            query = query.filter(PatientModel.current_department_id == department_id)
        return query

    def get_all(
        self,
        status: Optional[PatientStatus] = None,
        department_id: Optional[int] = None,
        limit: Optional[int] = None,
        offset: int = 0,
    ) -> List[Patient]:
        query = self._base_query(status, department_id).order_by(
            PatientModel.created_at.desc(), PatientModel.id.desc()
        )
        return [m.to_entity() for m in self._paginate(query, limit, offset).all()]

    def count(self, status: Optional[PatientStatus] = None, department_id: Optional[int] = None) -> int:
        return self._count(self._base_query(status, department_id))

    def create(self, patient: Patient) -> Patient:
        model = PatientModel.from_entity(patient)
        self.db.add(model)
        self.db.flush()
        return model.to_entity()

    def update(self, patient: Patient) -> Patient:
        model = self.db.get(PatientModel, patient.id)
        if not model:
            raise ValueError(f"Patient with id {patient.id} not found")

        model.name = patient.name
        model.age = patient.age
        model.gender = patient.gender
        model.medical_record_number = patient.medical_record_number
        model.current_status = patient.current_status.value
        model.current_department_id = patient.current_department_id
        model.current_bed_id = patient.current_bed_id
        model.admitted_at = patient.admitted_at
        model.discharged_at = patient.discharged_at

        self.db.flush()
        return model.to_entity()

    # ------------------------------------------------------------------
    # Atomic compare-and-set operations
    # ------------------------------------------------------------------
    def link_bed(
        self,
        patient_id: int,
        bed_id: int,
        department_id: int,
        new_status: PatientStatus,
        expected_statuses: List[PatientStatus],
        expected_bed_id: Optional[int],
        admitted_at: Optional[datetime] = None,
    ) -> bool:
        """Move a patient into a bed only if the patient is still in the state
        we validated (status + current bed). Returns False if another
        transaction changed the patient in the meantime."""
        values = {
            "current_bed_id": bed_id,
            "current_department_id": department_id,
            "current_status": new_status.value,
        }
        if admitted_at is not None:
            values["admitted_at"] = admitted_at
        stmt = (
            update(PatientModel)
            .where(
                PatientModel.id == patient_id,
                PatientModel.current_status.in_([s.value for s in expected_statuses]),
                PatientModel.current_bed_id.is_(None)
                if expected_bed_id is None
                else PatientModel.current_bed_id == expected_bed_id,
            )
            .values(**values)
        )
        return self.db.execute(stmt).rowcount == 1

    def unlink_bed_for_discharge(self, patient_id: int, expected_bed_id: Optional[int], discharged_at: datetime) -> bool:
        stmt = (
            update(PatientModel)
            .where(
                PatientModel.id == patient_id,
                PatientModel.current_status.in_([PatientStatus.ADMITTED.value, PatientStatus.TRANSFERRED.value]),
                PatientModel.current_bed_id.is_(None)
                if expected_bed_id is None
                else PatientModel.current_bed_id == expected_bed_id,
            )
            .values(
                current_bed_id=None,
                current_status=PatientStatus.DISCHARGED.value,
                discharged_at=discharged_at,
            )
        )
        return self.db.execute(stmt).rowcount == 1
