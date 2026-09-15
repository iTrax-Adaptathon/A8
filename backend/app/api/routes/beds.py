from typing import List, Optional
from fastapi import APIRouter, Depends, Query, Response, status
from app.api.pagination import PaginationParams, get_pagination, set_total_count
from app.api.routes._helpers import auto_assignment_schema
from app.api.schemas import (
    BedCreateSchema,
    BedStatusUpdateSchema,
    BedReleaseSchema,
    BedResponseSchema,
    BedReleaseResponseSchema,
)
from app.application import BedService
from app.core.dependencies import get_actor, get_bed_service, get_release_orchestrator
from app.domain.entities import Actor, Bed
from app.domain.enums import BedStatus, BedType
from app.domain.policies import NotFoundError
from app.orchestration.release_orchestration_service import ReleaseOrchestrationService

router = APIRouter(prefix="/beds", tags=["Beds"])


def _release_response(outcome) -> BedReleaseResponseSchema:
    return BedReleaseResponseSchema(
        bed=BedResponseSchema.model_validate(outcome.resource),
        auto_assignment=auto_assignment_schema(outcome.auto_assignment) if outcome.auto_assignment else None,
    )


@router.get("", response_model=List[BedResponseSchema], summary="List beds")
def list_beds(
    response: Response,
    department_id: Optional[int] = Query(None, alias="departmentId", description="Filter by department ID"),
    status: Optional[BedStatus] = Query(None, description="Filter by status"),
    bed_type: Optional[BedType] = Query(None, alias="bedType", description="Filter by bed type"),
    include_inactive: bool = Query(False, alias="includeInactive", description="Include deactivated beds"),
    pagination: PaginationParams = Depends(get_pagination),
    bed_service: BedService = Depends(get_bed_service),
):
    beds = bed_service.list_beds(
        department_id=department_id, status=status, bed_type=bed_type, include_inactive=include_inactive,
        limit=pagination.limit, offset=pagination.offset,
    )
    set_total_count(response, bed_service.count_beds(department_id, status, bed_type, include_inactive))
    return [BedResponseSchema.model_validate(b) for b in beds]


@router.get("/available", response_model=List[BedResponseSchema], summary="List assignable (AVAILABLE, active) beds")
def list_available_beds(
    response: Response,
    department_id: Optional[int] = Query(None, alias="departmentId", description="Filter by department ID"),
    pagination: PaginationParams = Depends(get_pagination),
    bed_service: BedService = Depends(get_bed_service),
):
    beds = bed_service.list_beds(
        department_id=department_id, status=BedStatus.AVAILABLE, limit=pagination.limit, offset=pagination.offset
    )
    set_total_count(response, bed_service.count_beds(department_id, BedStatus.AVAILABLE))
    return [BedResponseSchema.model_validate(b) for b in beds]


@router.get("/{id}", response_model=BedResponseSchema, summary="Get bed details")
def get_bed(
    id: int,
    bed_service: BedService = Depends(get_bed_service),
):
    bed = bed_service.get_bed(id)
    if not bed:
        raise NotFoundError(f"Bed with id {id} not found")
    return BedResponseSchema.model_validate(bed)


@router.post("", response_model=BedResponseSchema, status_code=status.HTTP_201_CREATED, summary="Create bed")
def create_bed(
    payload: BedCreateSchema,
    bed_service: BedService = Depends(get_bed_service),
    actor: Actor = Depends(get_actor),
):
    bed = Bed(
        id=None,
        bed_number=payload.bed_number,
        bed_type=payload.bed_type,
        department_id=payload.department_id,
        status=payload.status,
    )
    created = bed_service.create_bed(bed, actor=actor)
    return BedResponseSchema.model_validate(created)


@router.patch(
    "/{id}/status",
    response_model=BedResponseSchema,
    summary="Manual bed status change (never for OCCUPIED beds)",
    description="Allowed: AVAILABLE->CLEANING|MAINTENANCE, CLEANING->AVAILABLE|MAINTENANCE, MAINTENANCE->AVAILABLE|CLEANING. "
    "An OCCUPIED bed cannot be changed here (409). When the bed becomes AVAILABLE the waiting queue is evaluated.",
)
def update_bed_status(
    id: int,
    payload: BedStatusUpdateSchema,
    orchestrator: ReleaseOrchestrationService = Depends(get_release_orchestrator),
    actor: Actor = Depends(get_actor),
):
    outcome = orchestrator.update_bed_status(id, payload.new_status, payload.notes or "", actor, payload.auto_assign)
    return BedResponseSchema.model_validate(outcome.resource)


@router.post(
    "/{id}/release",
    response_model=BedReleaseResponseSchema,
    summary="Release bed: CLEANING -> AVAILABLE, then deterministic matching",
)
def release_bed(
    id: int,
    payload: BedReleaseSchema = None,
    orchestrator: ReleaseOrchestrationService = Depends(get_release_orchestrator),
    actor: Actor = Depends(get_actor),
):
    payload = payload or BedReleaseSchema()
    outcome = orchestrator.release_bed(id, payload.notes or "Bed cleaned", actor, payload.auto_assign)
    return _release_response(outcome)


@router.delete("/{id}", response_model=BedResponseSchema, summary="Deactivate bed (soft delete; history is kept)")
def deactivate_bed(
    id: int,
    bed_service: BedService = Depends(get_bed_service),
    actor: Actor = Depends(get_actor),
):
    updated = bed_service.deactivate_bed(id, actor=actor)
    return BedResponseSchema.model_validate(updated)
