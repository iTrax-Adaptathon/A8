from typing import Dict, List, Optional
from sqlalchemy import func, update
from sqlalchemy.orm import Session
from app.infrastructure.database.models import BedModel
from app.infrastructure.repositories.base import BaseRepository
from app.domain.entities import Bed
from app.domain.enums import BedStatus, BedType


class BedRepository(BaseRepository):
    def __init__(self, db: Session):
        super().__init__(db)

    def get_by_id(self, bed_id: int) -> Optional[Bed]:
        model = self.db.get(BedModel, bed_id)
        return model.to_entity() if model else None

    def _base_query(
        self,
        department_id: Optional[int] = None,
        status: Optional[BedStatus] = None,
        bed_type: Optional[BedType] = None,
        include_inactive: bool = False,
    ):
        query = self.db.query(BedModel)
        if not include_inactive:
            query = query.filter(BedModel.is_active.is_(True))
        if department_id:
            query = query.filter(BedModel.department_id == department_id)
        if status:
            query = query.filter(BedModel.status == status.value)
        if bed_type:
            query = query.filter(BedModel.bed_type == bed_type.value)
        return query

    def get_all(
        self,
        department_id: Optional[int] = None,
        status: Optional[BedStatus] = None,
        bed_type: Optional[BedType] = None,
        include_inactive: bool = False,
        limit: Optional[int] = None,
        offset: int = 0,
    ) -> List[Bed]:
        query = self._base_query(department_id, status, bed_type, include_inactive)
        query = query.order_by(BedModel.bed_number.asc(), BedModel.id.asc())
        return [m.to_entity() for m in self._paginate(query, limit, offset).all()]

    def count(
        self,
        department_id: Optional[int] = None,
        status: Optional[BedStatus] = None,
        bed_type: Optional[BedType] = None,
        include_inactive: bool = False,
    ) -> int:
        return self._count(self._base_query(department_id, status, bed_type, include_inactive))

    def count_by_status(self, department_id: Optional[int] = None) -> Dict[str, int]:
        """Counts of ACTIVE beds per status (inactive beds never count as capacity)."""
        query = self.db.query(BedModel.status, func.count(BedModel.id)).filter(BedModel.is_active.is_(True))
        if department_id:
            query = query.filter(BedModel.department_id == department_id)
        counts = {s.value: 0 for s in BedStatus}
        for status_value, n in query.group_by(BedModel.status).all():
            counts[status_value] = n
        return counts

    def create(self, bed: Bed) -> Bed:
        model = BedModel.from_entity(bed)
        self.db.add(model)
        self.db.flush()
        return model.to_entity()

    def update(self, bed: Bed) -> Bed:
        model = self.db.get(BedModel, bed.id)
        if not model:
            raise ValueError(f"Bed with id {bed.id} not found")

        model.bed_number = bed.bed_number
        model.bed_type = bed.bed_type.value
        model.department_id = bed.department_id
        model.status = bed.status.value
        model.current_patient_id = bed.current_patient_id
        model.is_active = bed.is_active

        self.db.flush()
        return model.to_entity()

    # ------------------------------------------------------------------
    # Atomic compare-and-set operations (SQLite-safe concurrency control).
    # Each is a single UPDATE whose WHERE clause encodes the expected state;
    # rowcount == 0 means another transaction won the claim.
    # ------------------------------------------------------------------
    def claim_for_patient(self, bed_id: int, patient_id: int) -> bool:
        result = self.db.execute(
            update(BedModel)
            .where(
                BedModel.id == bed_id,
                BedModel.status == BedStatus.AVAILABLE.value,
                BedModel.current_patient_id.is_(None),
                BedModel.is_active.is_(True),
            )
            .values(status=BedStatus.OCCUPIED.value, current_patient_id=patient_id)
        )
        return result.rowcount == 1

    def release_from_patient(self, bed_id: int, patient_id: int, new_status: BedStatus = BedStatus.CLEANING) -> bool:
        result = self.db.execute(
            update(BedModel)
            .where(
                BedModel.id == bed_id,
                BedModel.status == BedStatus.OCCUPIED.value,
                BedModel.current_patient_id == patient_id,
            )
            .values(status=new_status.value, current_patient_id=None)
        )
        return result.rowcount == 1

    def set_status_if(self, bed_id: int, expected: BedStatus, new_status: BedStatus) -> bool:
        result = self.db.execute(
            update(BedModel)
            .where(
                BedModel.id == bed_id,
                BedModel.status == expected.value,
                BedModel.current_patient_id.is_(None),
                BedModel.is_active.is_(True),
            )
            .values(status=new_status.value)
        )
        return result.rowcount == 1

    def deactivate_by_department(self, department_id: int) -> int:
        result = self.db.execute(
            update(BedModel)
            .where(BedModel.department_id == department_id, BedModel.is_active.is_(True))
            .values(is_active=False)
        )
        return result.rowcount
