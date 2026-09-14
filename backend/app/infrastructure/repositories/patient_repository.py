from typing import List, Optional
from sqlalchemy.orm import Session
from app.infrastructure.database.models import PatientModel
from app.domain.entities import Patient
from app.domain.enums import PatientStatus


class PatientRepository:
    def __init__(self, db: Session):
        self.db = db

    def get_by_id(self, patient_id: int) -> Optional[Patient]:
        model = self.db.query(PatientModel).filter(PatientModel.id == patient_id).first()
        return model.to_entity() if model else None

    def get_all(
        self,
        status: Optional[PatientStatus] = None,
        department_id: Optional[int] = None,
    ) -> List[Patient]:
        query = self.db.query(PatientModel)
        if status:
            query = query.filter(PatientModel.current_status == status.value)
        if department_id:
            query = query.filter(PatientModel.current_department_id == department_id)
        models = query.order_by(PatientModel.created_at.desc()).all()
        return [m.to_entity() for m in models]

    def create(self, patient: Patient) -> Patient:
        model = PatientModel.from_entity(patient)
        self.db.add(model)
        self.db.commit()
        self.db.refresh(model)
        return model.to_entity()

    def update(self, patient: Patient) -> Patient:
        model = self.db.query(PatientModel).filter(PatientModel.id == patient.id).first()
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

        self.db.commit()
        self.db.refresh(model)
        return model.to_entity()
