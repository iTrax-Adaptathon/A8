from typing import List, Optional
from fastapi import APIRouter, Depends, Query, Response
from app.api.pagination import PaginationParams, get_pagination, set_total_count
from app.api.schemas import FlowEventResponseSchema
from app.infrastructure.repositories import FlowEventRepository
from app.core.dependencies import get_flow_event_repo
from app.domain.enums import FlowEventType, ResourceType

router = APIRouter(prefix="/flow-events", tags=["Flow Events / Audit"])


@router.get(
    "",
    response_model=List[FlowEventResponseSchema],
    summary="List audit / flow events (newest first)",
    description="Immutable audit log of every state-changing operation, including actor, previous/new state and source.",
)
def list_flow_events(
    response: Response,
    patient_id: Optional[int] = Query(None, alias="patientId", description="Filter by patient ID"),
    resource_type: Optional[ResourceType] = Query(None, alias="resourceType", description="Filter by resource type"),
    resource_id: Optional[int] = Query(None, alias="resourceId", description="Filter by resource ID"),
    event_type: Optional[FlowEventType] = Query(None, alias="eventType", description="Filter by event type"),
    department_id: Optional[int] = Query(None, alias="departmentId", description="Filter by department ID"),
    pagination: PaginationParams = Depends(get_pagination),
    flow_repo: FlowEventRepository = Depends(get_flow_event_repo),
):
    events = flow_repo.get_all(
        patient_id=patient_id,
        limit=pagination.limit,
        offset=pagination.offset,
        resource_type=resource_type,
        resource_id=resource_id,
        event_type=event_type,
        department_id=department_id,
    )
    set_total_count(
        response,
        flow_repo.count(patient_id, resource_type, resource_id, event_type, department_id),
    )
    return [FlowEventResponseSchema.model_validate(e) for e in events]
