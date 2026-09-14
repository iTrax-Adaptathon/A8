from typing import List, Optional
from fastapi import APIRouter, Depends, Query
from app.api.schemas import FlowEventResponseSchema
from app.infrastructure.repositories import FlowEventRepository
from app.core.dependencies import get_flow_event_repo

router = APIRouter(prefix="/flow-events", tags=["Patient Flow"])


@router.get("", response_model=List[FlowEventResponseSchema], summary="List patient flow events")
def list_flow_events(
    patient_id: Optional[int] = Query(None, description="Filter by patient ID"),
    limit: int = Query(100, ge=1, le=1000, description="Limit max events"),
    flow_repo: FlowEventRepository = Depends(get_flow_event_repo),
):
    events = flow_repo.get_all(patient_id=patient_id, limit=limit)
    return [FlowEventResponseSchema.model_validate(e) for e in events]
