from typing import List, Optional
from sqlalchemy.orm import Session
from app.infrastructure.database.models import FlowEventModel
from app.domain.entities import FlowEvent


class FlowEventRepository:
    def __init__(self, db: Session):
        self.db = db

    def get_all(self, patient_id: Optional[int] = None, limit: int = 100) -> List[FlowEvent]:
        query = self.db.query(FlowEventModel)
        if patient_id:
            query = query.filter(FlowEventModel.patient_id == patient_id)
        models = query.order_by(FlowEventModel.timestamp.desc()).limit(limit).all()
        return [m.to_entity() for m in models]

    def create(self, event: FlowEvent) -> FlowEvent:
        model = FlowEventModel.from_entity(event)
        self.db.add(model)
        self.db.commit()
        self.db.refresh(model)
        return model.to_entity()
