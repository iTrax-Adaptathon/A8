from datetime import datetime
from typing import Dict, List, Optional
from sqlalchemy import func, update
from sqlalchemy.orm import Session
from app.infrastructure.database.models import WaitlistEntryModel
from app.infrastructure.repositories.base import BaseRepository
from app.domain.entities import WaitlistEntry
from app.domain.enums import WaitlistResourceType, WaitlistStatus


class WaitlistRepository(BaseRepository):
    """Queue ordering (see WaitlistPolicy): priority ASC, requested_at ASC, id ASC."""

    def __init__(self, db: Session):
        super().__init__(db)

    def get_by_id(self, entry_id: int) -> Optional[WaitlistEntry]:
        model = self.db.get(WaitlistEntryModel, entry_id)
        return model.to_entity() if model else None

    def _base_query(
        self,
        resource_type: Optional[WaitlistResourceType] = None,
        department_id: Optional[int] = None,
        status: Optional[WaitlistStatus] = None,
        patient_id: Optional[int] = None,
    ):
        query = self.db.query(WaitlistEntryModel)
        if resource_type:
            query = query.filter(WaitlistEntryModel.resource_type == resource_type.value)
        if department_id:
            query = query.filter(WaitlistEntryModel.department_id == department_id)
        if status:
            query = query.filter(WaitlistEntryModel.status == status.value)
        if patient_id:
            query = query.filter(WaitlistEntryModel.patient_id == patient_id)
        return query

    @staticmethod
    def _queue_order(query):
        return query.order_by(
            WaitlistEntryModel.priority.asc(),
            WaitlistEntryModel.requested_at.asc(),
            WaitlistEntryModel.id.asc(),
        )

    def get_all(
        self,
        resource_type: Optional[WaitlistResourceType] = None,
        department_id: Optional[int] = None,
        status: Optional[WaitlistStatus] = None,
        patient_id: Optional[int] = None,
        limit: Optional[int] = None,
        offset: int = 0,
    ) -> List[WaitlistEntry]:
        query = self._queue_order(self._base_query(resource_type, department_id, status, patient_id))
        return [m.to_entity() for m in self._paginate(query, limit, offset).all()]

    def count(
        self,
        resource_type: Optional[WaitlistResourceType] = None,
        department_id: Optional[int] = None,
        status: Optional[WaitlistStatus] = None,
        patient_id: Optional[int] = None,
    ) -> int:
        return self._count(self._base_query(resource_type, department_id, status, patient_id))

    def get_waiting_queue(
        self,
        resource_type: WaitlistResourceType,
        department_id: Optional[int] = None,
    ) -> List[WaitlistEntry]:
        return self.get_all(resource_type=resource_type, department_id=department_id, status=WaitlistStatus.WAITING)

    def waiting_counts_by_resource_type(self) -> Dict[str, int]:
        counts = {t.value: 0 for t in WaitlistResourceType}
        rows = (
            self.db.query(WaitlistEntryModel.resource_type, func.count(WaitlistEntryModel.id))
            .filter(WaitlistEntryModel.status == WaitlistStatus.WAITING.value)
            .group_by(WaitlistEntryModel.resource_type)
            .all()
        )
        for resource_type, n in rows:
            counts[resource_type] = n
        return counts

    def find_waiting_for_patient(
        self, patient_id: int, resource_type: WaitlistResourceType, surgery_id: Optional[int] = None
    ) -> Optional[WaitlistEntry]:
        query = self.db.query(WaitlistEntryModel).filter(
            WaitlistEntryModel.patient_id == patient_id,
            WaitlistEntryModel.resource_type == resource_type.value,
            WaitlistEntryModel.status == WaitlistStatus.WAITING.value,
        )
        if surgery_id is not None:
            query = query.filter(WaitlistEntryModel.surgery_id == surgery_id)
        model = query.order_by(WaitlistEntryModel.id.asc()).first()
        return model.to_entity() if model else None

    def create(self, entry: WaitlistEntry) -> WaitlistEntry:
        model = WaitlistEntryModel.from_entity(entry)
        self.db.add(model)
        self.db.flush()
        return model.to_entity()

    # Atomic compare-and-set
    def resolve_if_waiting(
        self,
        entry_id: int,
        new_status: WaitlistStatus,
        fulfilled_at: Optional[datetime] = None,
        fulfilled_resource_id: Optional[int] = None,
    ) -> bool:
        result = self.db.execute(
            update(WaitlistEntryModel)
            .where(
                WaitlistEntryModel.id == entry_id,
                WaitlistEntryModel.status == WaitlistStatus.WAITING.value,
            )
            .values(status=new_status.value, fulfilled_at=fulfilled_at, fulfilled_resource_id=fulfilled_resource_id)
        )
        return result.rowcount == 1
