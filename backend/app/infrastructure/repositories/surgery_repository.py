from typing import Dict, List, Optional
from sqlalchemy import func, update
from sqlalchemy.orm import Session
from app.infrastructure.database.models import SurgeryModel
from app.infrastructure.repositories.base import BaseRepository
from app.domain.entities import Surgery
from app.domain.enums import SurgeryStatus


class SurgeryRepository(BaseRepository):
    def __init__(self, db: Session):
        super().__init__(db)

    def get_by_id(self, surgery_id: int) -> Optional[Surgery]:
        model = self.db.get(SurgeryModel, surgery_id)
        return model.to_entity() if model else None

    def _base_query(
        self,
        status: Optional[SurgeryStatus] = None,
        department_id: Optional[int] = None,
        patient_id: Optional[int] = None,
        theatre_id: Optional[int] = None,
    ):
        query = self.db.query(SurgeryModel)
        if status:
            query = query.filter(SurgeryModel.status == status.value)
        if department_id:
            query = query.filter(SurgeryModel.department_id == department_id)
        if patient_id:
            query = query.filter(SurgeryModel.patient_id == patient_id)
        if theatre_id:
            query = query.filter(SurgeryModel.theatre_id == theatre_id)
        return query

    def get_all(
        self,
        status: Optional[SurgeryStatus] = None,
        department_id: Optional[int] = None,
        patient_id: Optional[int] = None,
        theatre_id: Optional[int] = None,
        limit: Optional[int] = None,
        offset: int = 0,
    ) -> List[Surgery]:
        # Deterministic: most urgent first, then oldest request, then id.
        query = self._base_query(status, department_id, patient_id, theatre_id).order_by(
            SurgeryModel.priority.asc(), SurgeryModel.created_at.asc(), SurgeryModel.id.asc()
        )
        return [m.to_entity() for m in self._paginate(query, limit, offset).all()]

    def count(
        self,
        status: Optional[SurgeryStatus] = None,
        department_id: Optional[int] = None,
        patient_id: Optional[int] = None,
        theatre_id: Optional[int] = None,
    ) -> int:
        return self._count(self._base_query(status, department_id, patient_id, theatre_id))

    def count_by_status(self) -> Dict[str, int]:
        counts = {s.value: 0 for s in SurgeryStatus}
        for status_value, n in self.db.query(SurgeryModel.status, func.count(SurgeryModel.id)).group_by(SurgeryModel.status).all():
            counts[status_value] = n
        return counts

    def create(self, surgery: Surgery) -> Surgery:
        model = SurgeryModel.from_entity(surgery)
        self.db.add(model)
        self.db.flush()
        return model.to_entity()

    def update(self, surgery: Surgery) -> Surgery:
        model = self.db.get(SurgeryModel, surgery.id)
        if not model:
            raise ValueError(f"Surgery with id {surgery.id} not found")
        model.patient_id = surgery.patient_id
        model.department_id = surgery.department_id
        model.procedure_name = surgery.procedure_name
        model.duration_minutes = surgery.duration_minutes
        model.priority = surgery.priority
        model.status = surgery.status.value
        model.theatre_id = surgery.theatre_id
        model.slot_id = surgery.slot_id
        model.required_staff_role = surgery.required_staff_role.value if surgery.required_staff_role else None
        model.scheduled_at = surgery.scheduled_at
        model.started_at = surgery.started_at
        model.completed_at = surgery.completed_at
        self.db.flush()
        return model.to_entity()

    def set_status_if(self, surgery_id: int, expected: SurgeryStatus, new_status: SurgeryStatus, **values) -> bool:
        result = self.db.execute(
            update(SurgeryModel)
            .where(SurgeryModel.id == surgery_id, SurgeryModel.status == expected.value)
            .values(status=new_status.value, **values)
        )
        return result.rowcount == 1
