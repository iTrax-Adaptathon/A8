from datetime import datetime
from typing import Dict, List, Optional
from sqlalchemy import func, update
from sqlalchemy.orm import Session
from app.infrastructure.database.models import StaffModel, StaffAssignmentModel
from app.infrastructure.repositories.base import BaseRepository
from app.domain.entities import Staff, StaffAssignment
from app.domain.enums import StaffRole, StaffStatus, StaffAssignmentStatus


class StaffRepository(BaseRepository):
    def __init__(self, db: Session):
        super().__init__(db)

    def get_by_id(self, staff_id: int) -> Optional[Staff]:
        model = self.db.get(StaffModel, staff_id)
        return model.to_entity() if model else None

    def _base_query(
        self,
        department_id: Optional[int] = None,
        role: Optional[StaffRole] = None,
        status: Optional[StaffStatus] = None,
        include_inactive: bool = False,
    ):
        query = self.db.query(StaffModel)
        if not include_inactive:
            query = query.filter(StaffModel.is_active.is_(True))
        if department_id:
            query = query.filter(StaffModel.department_id == department_id)
        if role:
            query = query.filter(StaffModel.role == role.value)
        if status:
            query = query.filter(StaffModel.status == status.value)
        return query

    def get_all(
        self,
        department_id: Optional[int] = None,
        role: Optional[StaffRole] = None,
        status: Optional[StaffStatus] = None,
        include_inactive: bool = False,
        limit: Optional[int] = None,
        offset: int = 0,
    ) -> List[Staff]:
        query = self._base_query(department_id, role, status, include_inactive).order_by(
            StaffModel.name.asc(), StaffModel.id.asc()
        )
        return [m.to_entity() for m in self._paginate(query, limit, offset).all()]

    def count(
        self,
        department_id: Optional[int] = None,
        role: Optional[StaffRole] = None,
        status: Optional[StaffStatus] = None,
        include_inactive: bool = False,
    ) -> int:
        return self._count(self._base_query(department_id, role, status, include_inactive))

    def count_by_status(self) -> Dict[str, int]:
        counts = {s.value: 0 for s in StaffStatus}
        rows = (
            self.db.query(StaffModel.status, func.count(StaffModel.id))
            .filter(StaffModel.is_active.is_(True))
            .group_by(StaffModel.status)
            .all()
        )
        for status_value, n in rows:
            counts[status_value] = n
        return counts

    def create(self, staff: Staff) -> Staff:
        model = StaffModel.from_entity(staff)
        self.db.add(model)
        self.db.flush()
        return model.to_entity()

    def set_status_if(self, staff_id: int, expected: StaffStatus, new_status: StaffStatus) -> bool:
        result = self.db.execute(
            update(StaffModel)
            .where(StaffModel.id == staff_id, StaffModel.status == expected.value, StaffModel.is_active.is_(True))
            .values(status=new_status.value)
        )
        return result.rowcount == 1

    def set_active(self, staff_id: int, is_active: bool) -> bool:
        result = self.db.execute(
            update(StaffModel)
            .where(StaffModel.id == staff_id, StaffModel.is_active.is_(not is_active))
            .values(is_active=is_active)
        )
        return result.rowcount == 1


class StaffAssignmentRepository(BaseRepository):
    def __init__(self, db: Session):
        super().__init__(db)

    def get_by_id(self, assignment_id: int) -> Optional[StaffAssignment]:
        model = self.db.get(StaffAssignmentModel, assignment_id)
        return model.to_entity() if model else None

    def _base_query(
        self,
        staff_id: Optional[int] = None,
        status: Optional[StaffAssignmentStatus] = None,
        surgery_id: Optional[int] = None,
        patient_id: Optional[int] = None,
    ):
        query = self.db.query(StaffAssignmentModel)
        if staff_id:
            query = query.filter(StaffAssignmentModel.staff_id == staff_id)
        if status:
            query = query.filter(StaffAssignmentModel.status == status.value)
        if surgery_id:
            query = query.filter(StaffAssignmentModel.surgery_id == surgery_id)
        if patient_id:
            query = query.filter(StaffAssignmentModel.patient_id == patient_id)
        return query

    def get_all(
        self,
        staff_id: Optional[int] = None,
        status: Optional[StaffAssignmentStatus] = None,
        surgery_id: Optional[int] = None,
        patient_id: Optional[int] = None,
        limit: Optional[int] = None,
        offset: int = 0,
    ) -> List[StaffAssignment]:
        query = self._base_query(staff_id, status, surgery_id, patient_id).order_by(
            StaffAssignmentModel.start_time.desc(), StaffAssignmentModel.id.desc()
        )
        return [m.to_entity() for m in self._paginate(query, limit, offset).all()]

    def count(
        self,
        staff_id: Optional[int] = None,
        status: Optional[StaffAssignmentStatus] = None,
        surgery_id: Optional[int] = None,
        patient_id: Optional[int] = None,
    ) -> int:
        return self._count(self._base_query(staff_id, status, surgery_id, patient_id))

    def get_active_for_staff(self, staff_id: int) -> Optional[StaffAssignment]:
        model = (
            self.db.query(StaffAssignmentModel)
            .filter(
                StaffAssignmentModel.staff_id == staff_id,
                StaffAssignmentModel.status == StaffAssignmentStatus.ACTIVE.value,
            )
            .first()
        )
        return model.to_entity() if model else None

    def get_active_for_surgery(self, surgery_id: int) -> List[StaffAssignment]:
        models = (
            self.db.query(StaffAssignmentModel)
            .filter(
                StaffAssignmentModel.surgery_id == surgery_id,
                StaffAssignmentModel.status == StaffAssignmentStatus.ACTIVE.value,
            )
            .order_by(StaffAssignmentModel.id.asc())
            .all()
        )
        return [m.to_entity() for m in models]

    def create(self, assignment: StaffAssignment) -> StaffAssignment:
        model = StaffAssignmentModel.from_entity(assignment)
        self.db.add(model)
        self.db.flush()
        return model.to_entity()

    def release_if_active(self, assignment_id: int, released_at: datetime) -> bool:
        result = self.db.execute(
            update(StaffAssignmentModel)
            .where(
                StaffAssignmentModel.id == assignment_id,
                StaffAssignmentModel.status == StaffAssignmentStatus.ACTIVE.value,
            )
            .values(status=StaffAssignmentStatus.RELEASED.value, released_at=released_at)
        )
        return result.rowcount == 1
