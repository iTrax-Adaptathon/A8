from datetime import datetime
from typing import List, Optional
from fastapi import APIRouter, Depends, Query, Response, status
from app.api.pagination import PaginationParams, get_pagination, set_total_count
from app.api.routes._helpers import auto_assignment_list, auto_assignment_schema
from app.api.schemas import (
    TheatreCreateSchema,
    TheatreStatusUpdateSchema,
    TheatreReleaseSchema,
    TheatreResponseSchema,
    TheatreReleaseResponseSchema,
    TheatreSlotCreateSchema,
    TheatreSlotCancelSchema,
    TheatreSlotResponseSchema,
    TheatreSlotCreateResponseSchema,
)
from app.application import TheatreService
from app.core.dependencies import get_actor, get_theatre_service, get_release_orchestrator
from app.domain.entities import Actor, Theatre
from app.domain.enums import TheatreSlotStatus, TheatreStatus
from app.domain.policies import NotFoundError
from app.orchestration.release_orchestration_service import ReleaseOrchestrationService

router = APIRouter(prefix="/theatres", tags=["Theatres"])
slots_router = APIRouter(prefix="/theatre-slots", tags=["Theatre Slots"])


# ---------------------------------------------------------------------------
# Theatres
# ---------------------------------------------------------------------------
@router.get("", response_model=List[TheatreResponseSchema], summary="List theatres")
def list_theatres(
    response: Response,
    department_id: Optional[int] = Query(None, alias="departmentId"),
    status: Optional[TheatreStatus] = Query(None),
    include_inactive: bool = Query(False, alias="includeInactive"),
    pagination: PaginationParams = Depends(get_pagination),
    service: TheatreService = Depends(get_theatre_service),
):
    theatres = service.list_theatres(department_id, status, include_inactive, pagination.limit, pagination.offset)
    set_total_count(response, service.count_theatres(department_id, status, include_inactive))
    return [TheatreResponseSchema.model_validate(t) for t in theatres]


@router.get("/{id}", response_model=TheatreResponseSchema, summary="Get theatre details")
def get_theatre(id: int, service: TheatreService = Depends(get_theatre_service)):
    theatre = service.get_theatre(id)
    if not theatre:
        raise NotFoundError(f"Theatre with id {id} not found")
    return TheatreResponseSchema.model_validate(theatre)


@router.post("", response_model=TheatreResponseSchema, status_code=status.HTTP_201_CREATED, summary="Create theatre")
def create_theatre(
    payload: TheatreCreateSchema,
    service: TheatreService = Depends(get_theatre_service),
    actor: Actor = Depends(get_actor),
):
    created = service.create_theatre(
        Theatre(id=None, name=payload.name, department_id=payload.department_id, status=payload.status), actor=actor
    )
    return TheatreResponseSchema.model_validate(created)


@router.patch(
    "/{id}/status",
    response_model=TheatreResponseSchema,
    summary="Manual theatre status change (IN_USE is controlled by surgeries)",
)
def update_theatre_status(
    id: int,
    payload: TheatreStatusUpdateSchema,
    orchestrator: ReleaseOrchestrationService = Depends(get_release_orchestrator),
    actor: Actor = Depends(get_actor),
):
    outcome = orchestrator.update_theatre_status(id, payload.new_status, payload.notes or "", actor, payload.auto_assign)
    return TheatreResponseSchema.model_validate(outcome.resource)


@router.post(
    "/{id}/release",
    response_model=TheatreReleaseResponseSchema,
    summary="Release theatre: CLEANING -> AVAILABLE, then match its AVAILABLE slots",
)
def release_theatre(
    id: int,
    payload: TheatreReleaseSchema = None,
    orchestrator: ReleaseOrchestrationService = Depends(get_release_orchestrator),
    actor: Actor = Depends(get_actor),
):
    payload = payload or TheatreReleaseSchema()
    outcome = orchestrator.release_theatre(id, payload.notes or "Theatre cleaned", actor, payload.auto_assign)
    return TheatreReleaseResponseSchema(
        theatre=TheatreResponseSchema.model_validate(outcome.resource),
        auto_assignments=auto_assignment_list(outcome.auto_assignments),
    )


@router.delete("/{id}", response_model=TheatreResponseSchema, summary="Deactivate theatre (soft delete)")
def deactivate_theatre(
    id: int,
    service: TheatreService = Depends(get_theatre_service),
    actor: Actor = Depends(get_actor),
):
    return TheatreResponseSchema.model_validate(service.deactivate_theatre(id, actor=actor))


# ---------------------------------------------------------------------------
# Slots
# ---------------------------------------------------------------------------
@slots_router.get("", response_model=List[TheatreSlotResponseSchema], summary="List theatre slots (by start time)")
def list_slots(
    response: Response,
    theatre_id: Optional[int] = Query(None, alias="theatreId"),
    status: Optional[TheatreSlotStatus] = Query(None),
    surgery_id: Optional[int] = Query(None, alias="surgeryId"),
    start_from: Optional[datetime] = Query(None, alias="startFrom", description="Only slots starting at/after (UTC)"),
    start_to: Optional[datetime] = Query(None, alias="startTo", description="Only slots starting at/before (UTC)"),
    pagination: PaginationParams = Depends(get_pagination),
    service: TheatreService = Depends(get_theatre_service),
):
    from app.domain.policies import to_naive_utc

    start_from, start_to = to_naive_utc(start_from), to_naive_utc(start_to)
    slots = service.list_slots(theatre_id, status, surgery_id, start_from, start_to, pagination.limit, pagination.offset)
    set_total_count(response, service.count_slots(theatre_id, status, surgery_id, start_from, start_to))
    return [TheatreSlotResponseSchema.model_validate(s) for s in slots]


@slots_router.get("/{id}", response_model=TheatreSlotResponseSchema, summary="Get theatre slot")
def get_slot(id: int, service: TheatreService = Depends(get_theatre_service)):
    slot = service.get_slot(id)
    if not slot:
        raise NotFoundError(f"Theatre slot with id {id} not found")
    return TheatreSlotResponseSchema.model_validate(slot)


@slots_router.post(
    "",
    response_model=TheatreSlotCreateResponseSchema,
    status_code=status.HTTP_201_CREATED,
    summary="Create theatre slot (no overlap, 15 min - 24 h); new AVAILABLE slot is matched against waiting surgeries",
)
def create_slot(
    payload: TheatreSlotCreateSchema,
    orchestrator: ReleaseOrchestrationService = Depends(get_release_orchestrator),
    actor: Actor = Depends(get_actor),
):
    outcome = orchestrator.create_slot(payload.theatre_id, payload.start_time, payload.end_time, actor, payload.auto_assign)
    return TheatreSlotCreateResponseSchema(
        slot=TheatreSlotResponseSchema.model_validate(outcome.resource),
        auto_assignment=auto_assignment_schema(outcome.auto_assignment) if outcome.auto_assignment else None,
    )


@slots_router.post("/{id}/cancel", response_model=TheatreSlotResponseSchema, summary="Cancel an AVAILABLE slot")
def cancel_slot(
    id: int,
    payload: TheatreSlotCancelSchema = None,
    service: TheatreService = Depends(get_theatre_service),
    actor: Actor = Depends(get_actor),
):
    payload = payload or TheatreSlotCancelSchema()
    return TheatreSlotResponseSchema.model_validate(service.cancel_slot(id, payload.notes or "", actor=actor))
