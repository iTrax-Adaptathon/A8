from typing import List, Optional
from sqlalchemy.orm import Session
from app.infrastructure.database.models import BedModel
from app.domain.entities import Bed
from app.domain.enums import BedStatus, BedType


class BedRepository:
    def __init__(self, db: Session):
        self.db = db

    def get_by_id(self, bed_id: int) -> Optional[Bed]:
        model = self.db.query(BedModel).filter(BedModel.id == bed_id).first()
        return model.to_entity() if model else None

    def get_all(
        self,
        department_id: Optional[int] = None,
        status: Optional[BedStatus] = None,
        bed_type: Optional[BedType] = None,
    ) -> List[Bed]:
        query = self.db.query(BedModel)
        if department_id:
            query = query.filter(BedModel.department_id == department_id)
        if status:
            query = query.filter(BedModel.status == status.value)
        if bed_type:
            query = query.filter(BedModel.bed_type == bed_type.value)
        models = query.order_by(BedModel.bed_number.asc()).all()
        return [m.to_entity() for m in models]

    def create(self, bed: Bed) -> Bed:
        model = BedModel.from_entity(bed)
        self.db.add(model)
        self.db.commit()
        self.db.refresh(model)
        return model.to_entity()

    def update(self, bed: Bed) -> Bed:
        model = self.db.query(BedModel).filter(BedModel.id == bed.id).first()
        if not model:
            raise ValueError(f"Bed with id {bed.id} not found")

        model.bed_number = bed.bed_number
        model.bed_type = bed.bed_type.value
        model.department_id = bed.department_id
        model.status = bed.status.value
        model.current_patient_id = bed.current_patient_id

        self.db.commit()
        self.db.refresh(model)
        return model.to_entity()
