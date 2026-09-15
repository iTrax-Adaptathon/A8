from typing import List, Optional
from fastapi import APIRouter, Depends, Query, Response, status
from app.api.pagination import PaginationParams, get_pagination, set_total_count
from app.api.routes._helpers import auto_assignment_list
from app.api.schemas import (
    SurgeryCreateSchema,
    SurgeryScheduleSchema,
    SurgeryActionSchema,
    SurgeryResponseSchema,
    SurgeryActionResponseSchema,
)
from app.application import SurgeryService
from app.core.dependencies import get_actor, get_surgery_service, get_release_orchestrator
from app.domain.entities import Actor, Surgery
from app.domain.enums import SurgeryStatus
from app.domain.policies import NotFoundError
from app.orchestration.release_orchestration_service import ReleaseOrchestrationService

router = APIRouter(prefix="/surgeries", tags=["Surgeries"])


def _action_response(outcome) -> SurgeryActionResponseSchema:
    return SurgeryActionResponseSchema(
        surgery=SurgeryResponseSchema.model_validate(outcome.resource),
        auto_assignments=auto_assignment_list(outcome.auto_assignments),
    )


@router.get("", response_model=List[SurgeryResponseSchema], summary="List surgeries (priority, then oldest first)")
def list_surgeries(
    response: Response,
    status: Optional[SurgeryStatus] = Query(None),
    department_id: Optional[int] = Query(None, alias="departmentId"),
    patient_id: Optional[int] = Query(None, alias="patientId"),
    theatre_id: Optional[int] = Query(None, alias="theatreId"),
    pagination: PaginationParams = Depends(get_pagination),
    service: SurgeryService = Depends(get_surgery_service),
):
    surgeries = service.list_surgeries(status, department_id, patient_id, theatre_id, pagination.limit, pagination.offset)
    set_total_count(response, service.count_surgeries(status, department_id, patient_id, theatre_id))
    return [SurgeryResponseSchema.model_validate(s) for s in surgeries]


@router.get("/{id}", response_model=SurgeryResponseSchema, summary="Get surgery")
def get_surgery(id: int, service: SurgeryService = Depends(get_surgery_service)):
    surgery = service.get_surgery(id)
    if not surgery:
        raise NotFoundError(f"Surgery with id {id} not found")
    return SurgeryResponseSchema.model_validate(surgery)


@router.post(
    "",
    response_model=SurgeryResponseSchema,
    status_code=status.HTTP_201_CREATED,
    summary="Create surgery (WAITING) and add it to the theatre waitlist",
)
def create_surgery(
    payload: SurgeryCreateSchema,
    service: SurgeryService = Depends(get_surgery_service),
    actor: Actor = Depends(get_actor),
):
    surgery = Surgery(
        id=None,
        patient_id=payload.patient_id,
        department_id=payload.department_id,
        procedure_name=payload.procedure_name,
        duration_minutes=payload.duration_minutes,
        priority=payload.priority,
        required_staff_role=payload.required_staff_role,
    )
    created = service.create_surgery(surgery, reason=payload.reason or "", actor=actor)
    return SurgeryResponseSchema.model_validate(created)


@router.post("/{id}/schedule", response_model=SurgeryResponseSchema, summary="Schedule surgery into a specific AVAILABLE slot")
def schedule_surgery(
    id: int,
    payload: SurgeryScheduleSchema,
    service: SurgeryService = Depends(get_surgery_service),
    actor: Actor = Depends(get_actor),
):
    return SurgeryResponseSchema.model_validate(service.schedule_surgery(id, payload.slot_id, payload.notes or "", actor=actor))


@router.post("/{id}/unschedule", response_model=SurgeryActionResponseSchema, summary="SCHEDULED -> WAITING; slot released and re-matched")
def unschedule_surgery(
    id: int,
    payload: SurgeryActionSchema = None,
    orchestrator: ReleaseOrchestrationService = Depends(get_release_orchestrator),
    actor: Actor = Depends(get_actor),
):
    payload = payload or SurgeryActionSchema()
    return _action_response(orchestrator.unschedule_surgery(id, payload.notes or "", actor, payload.auto_assign))


@router.post("/{id}/start", response_model=SurgeryResponseSchema, summary="SCHEDULED -> IN_PROGRESS (theatre -> IN_USE)")
def start_surgery(
    id: int,
    payload: SurgeryActionSchema = None,
    service: SurgeryService = Depends(get_surgery_service),
    actor: Actor = Depends(get_actor),
):
    payload = payload or SurgeryActionSchema()
    return SurgeryResponseSchema.model_validate(service.start_surgery(id, payload.notes or "", actor=actor))


@router.post("/{id}/complete", response_model=SurgeryActionResponseSchema, summary="IN_PROGRESS -> COMPLETED (theatre -> CLEANING, staff released)")
def complete_surgery(
    id: int,
    payload: SurgeryActionSchema = None,
    orchestrator: ReleaseOrchestrationService = Depends(get_release_orchestrator),
    actor: Actor = Depends(get_actor),
):
    payload = payload or SurgeryActionSchema()
    return _action_response(orchestrator.complete_surgery(id, payload.notes or "", actor, payload.auto_assign))


@router.post("/{id}/cancel", response_model=SurgeryActionResponseSchema, summary="WAITING/SCHEDULED -> CANCELLED (slot + staff released)")
def cancel_surgery(
    id: int,
    payload: SurgeryActionSchema = None,
    orchestrator: ReleaseOrchestrationService = Depends(get_release_orchestrator),
    actor: Actor = Depends(get_actor),
):
    payload = payload or SurgeryActionSchema()
    return _action_response(orchestrator.cancel_surgery(id, payload.notes or "", actor, payload.auto_assign))
