from datetime import datetime
from typing import Any, Dict, Optional
from app.api.schemas.base import CamelModel
from app.domain.enums import EventSource, FlowEventType, ResourceType


class FlowEventResponseSchema(CamelModel):
    """One immutable audit record."""

    id: int
    event_type: FlowEventType
    patient_id: Optional[int] = None
    from_department_id: Optional[int] = None
    to_department_id: Optional[int] = None
    from_bed_id: Optional[int] = None
    to_bed_id: Optional[int] = None
    timestamp: datetime
    notes: str
    resource_type: Optional[ResourceType] = None
    resource_id: Optional[int] = None
    department_id: Optional[int] = None
    previous_state: Optional[str] = None
    new_state: Optional[str] = None
    actor_id: str
    actor_name: str
    source: EventSource
    metadata: Dict[str, Any] = {}
