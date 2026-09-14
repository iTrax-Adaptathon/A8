from datetime import datetime
from typing import Optional
from pydantic import BaseModel, ConfigDict
from app.domain.enums import FlowEventType


class FlowEventResponseSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    event_type: FlowEventType
    patient_id: int
    from_department_id: Optional[int] = None
    to_department_id: Optional[int] = None
    from_bed_id: Optional[int] = None
    to_bed_id: Optional[int] = None
    timestamp: datetime
    notes: str
