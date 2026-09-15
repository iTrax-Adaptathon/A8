from typing import List, Optional
from sqlalchemy.orm import Session
from app.infrastructure.database.models import FlowEventModel
from app.infrastructure.repositories.base import BaseRepository
from app.domain.entities import FlowEvent
from app.domain.enums import FlowEventType, ResourceType


class FlowEventRepository(BaseRepository):
    """Append-only. There is intentionally no update or delete method."""

    def __init__(self, db: Session):
        super().__init__(db)

    def _base_query(
        self,
        patient_id: Optional[int] = None,
        resource_type: Optional[ResourceType] = None,
        resource_id: Optional[int] = None,
        event_type: Optional[FlowEventType] = None,
        department_id: Optional[int] = None,
    ):
        query = self.db.query(FlowEventModel)
        if patient_id:
            query = query.filter(FlowEventModel.patient_id == patient_id)
        if resource_type:
            query = query.filter(FlowEventModel.resource_type == resource_type.value)
        if resource_id:
            query = query.filter(FlowEventModel.resource_id == resource_id)
        if event_type:
            query = query.filter(FlowEventModel.event_type == event_type.value)
        if department_id:
            query = query.filter(FlowEventModel.department_id == department_id)
        return query

    def get_all(
        self,
        patient_id: Optional[int] = None,
        limit: Optional[int] = 100,
        offset: int = 0,
        resource_type: Optional[ResourceType] = None,
        resource_id: Optional[int] = None,
        event_type: Optional[FlowEventType] = None,
        department_id: Optional[int] = None,
    ) -> List[FlowEvent]:
        query = self._base_query(patient_id, resource_type, resource_id, event_type, department_id)
        query = query.order_by(FlowEventModel.timestamp.desc(), FlowEventModel.id.desc())
        return [m.to_entity() for m in self._paginate(query, limit, offset).all()]

    def count(
        self,
        patient_id: Optional[int] = None,
        resource_type: Optional[ResourceType] = None,
        resource_id: Optional[int] = None,
        event_type: Optional[FlowEventType] = None,
        department_id: Optional[int] = None,
    ) -> int:
        return self._count(self._base_query(patient_id, resource_type, resource_id, event_type, department_id))

    def get_patient_history(self, patient_id: int, limit: Optional[int] = None, offset: int = 0) -> List[FlowEvent]:
        """Complete chronological timeline for one patient (oldest first)."""
        query = (
            self.db.query(FlowEventModel)
            .filter(FlowEventModel.patient_id == patient_id)
            .order_by(FlowEventModel.timestamp.asc(), FlowEventModel.id.asc())
        )
        return [m.to_entity() for m in self._paginate(query, limit, offset).all()]

    def create(self, event: FlowEvent) -> FlowEvent:
        model = FlowEventModel.from_entity(event)
        self.db.add(model)
        self.db.flush()
        return model.to_entity()
