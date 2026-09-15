from typing import Dict, List, Optional
from sqlalchemy import func, update
from sqlalchemy.orm import Session
from app.infrastructure.database.models import DepartmentModel, BedModel
from app.infrastructure.repositories.base import BaseRepository
from app.domain.entities import Department
from app.domain.enums import BedStatus


class DepartmentRepository(BaseRepository):
    def __init__(self, db: Session):
        super().__init__(db)

    def _bed_counts(self, department_id: int) -> Dict[str, int]:
        counts = {s.value: 0 for s in BedStatus}
        rows = (
            self.db.query(BedModel.status, func.count(BedModel.id))
            .filter(BedModel.department_id == department_id, BedModel.is_active.is_(True))
            .group_by(BedModel.status)
            .all()
        )
        for status_value, n in rows:
            counts[status_value] = n
        return counts

    def _to_entity(self, model: DepartmentModel) -> Department:
        counts = self._bed_counts(model.id)
        return model.to_entity(
            occupied_count=counts[BedStatus.OCCUPIED.value],
            total_beds=sum(counts.values()),
        )

    def bed_status_counts(self, department_id: int) -> Dict[str, int]:
        return self._bed_counts(department_id)

    def get_by_id(self, department_id: int) -> Optional[Department]:
        model = self.db.get(DepartmentModel, department_id)
        return self._to_entity(model) if model else None

    def _base_query(self, include_inactive: bool = False):
        query = self.db.query(DepartmentModel)
        if not include_inactive:
            query = query.filter(DepartmentModel.is_active.is_(True))
        return query

    def get_all(self, include_inactive: bool = False, limit: Optional[int] = None, offset: int = 0) -> List[Department]:
        query = self._base_query(include_inactive).order_by(DepartmentModel.name.asc(), DepartmentModel.id.asc())
        return [self._to_entity(m) for m in self._paginate(query, limit, offset).all()]

    def count(self, include_inactive: bool = False) -> int:
        return self._count(self._base_query(include_inactive))

    def create(self, department: Department) -> Department:
        model = DepartmentModel.from_entity(department)
        self.db.add(model)
        self.db.flush()
        return model.to_entity(occupied_count=0, total_beds=0)

    def set_active(self, department_id: int, is_active: bool) -> bool:
        result = self.db.execute(
            update(DepartmentModel)
            .where(DepartmentModel.id == department_id, DepartmentModel.is_active.is_(not is_active))
            .values(is_active=is_active)
        )
        return result.rowcount == 1
