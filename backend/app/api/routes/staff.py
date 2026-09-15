from typing import List, Optional
from fastapi import APIRouter, Depends, Query, Response, status
from app.api.pagination import PaginationParams, get_pagination, set_total_count
from app.api.routes._helpers import auto_assignment_schema
from app.api.schemas import (
    StaffCreateSchema,
    StaffStatusUpdateSchema,
    StaffAssignSchema,
    StaffAssignmentReleaseSchema,
    StaffResponseSchema,
    StaffAssignmentResponseSchema,
    StaffAssignmentReleaseResponseSchema,
)
from app.application import StaffService
from app.core.dependencies import get_actor, get_staff_service, get_release_orchestrator
from app.domain.entities import Actor, Staff
from app.domain.enums import StaffAssignmentStatus, StaffRole, StaffStatus
from app.domain.policies import NotFoundError
from app.orchestration.release_orchestration_service import ReleaseOrchestrationService

router = APIRouter(prefix="/staff", tags=["Staff"])
assignments_router = APIRouter(prefix="/staff-assignments", tags=["Staff Assignments"])


@router.get("", response_model=List[StaffResponseSchema], summary="List staff")
def list_staff(
    response: Response,
    department_id: Optional[int] = Query(None, alias="departmentId"),
    role: Optional[StaffRole] = Query(None),
    status: Optional[StaffStatus] = Query(None),
    include_inactive: bool = Query(False, alias="includeInactive"),
    pagination: PaginationParams = Depends(get_pagination),
    service: StaffService = Depends(get_staff_service),
):
    staff = service.list_staff(department_id, role, status, include_inactive, pagination.limit, pagination.offset)
    set_total_count(response, service.count_staff(department_id, role, status, include_inactive))
    return [StaffResponseSchema.model_validate(s) for s in staff]


@router.get("/{id}", response_model=StaffResponseSchema, summary="Get staff member")
def get_staff(id: int, service: StaffService = Depends(get_staff_service)):
    staff = service.get_staff(id)
    if not staff:
        raise NotFoundError(f"Staff with id {id} not found")
    return StaffResponseSchema.model_validate(staff)


@router.post("", response_model=StaffResponseSchema, status_code=status.HTTP_201_CREATED, summary="Create staff member")
def create_staff(
    payload: StaffCreateSchema,
    service: StaffService = Depends(get_staff_service),
    actor: Actor = Depends(get_actor),
):
    created = service.create_staff(
        Staff(
            id=None,
            name=payload.name,
            role=payload.role,
            department_id=payload.department_id,
            shift_start=payload.shift_start,
            shift_end=payload.shift_end,
            status=payload.status,
        ),
        actor=actor,
    )
    return StaffResponseSchema.model_validate(created)


@router.patch("/{id}/status", response_model=StaffResponseSchema, summary="AVAILABLE <-> OFF_DUTY (ASSIGNED is set by assignments)")
def update_staff_status(
    id: int,
    payload: StaffStatusUpdateSchema,
    orchestrator: ReleaseOrchestrationService = Depends(get_release_orchestrator),
    actor: Actor = Depends(get_actor),
):
    outcome = orchestrator.update_staff_status(id, payload.new_status, payload.notes or "", actor, payload.auto_assign)
    return StaffResponseSchema.model_validate(outcome.resource)


@router.post(
    "/{id}/assign",
    response_model=StaffAssignmentResponseSchema,
    status_code=status.HTTP_201_CREATED,
    summary="Assign staff to a surgery or patient (role, department, shift and availability validated)",
)
def assign_staff(
    id: int,
    payload: StaffAssignSchema,
    service: StaffService = Depends(get_staff_service),
    actor: Actor = Depends(get_actor),
):
    assignment = service.assign_staff(
        id, payload.assignment_type, payload.surgery_id, payload.patient_id,
        required_role=payload.required_role, notes=payload.notes or "", actor=actor,
    )
    return StaffAssignmentResponseSchema.model_validate(assignment)


@router.delete("/{id}", response_model=StaffResponseSchema, summary="Deactivate staff member (soft delete)")
def deactivate_staff(
    id: int,
    service: StaffService = Depends(get_staff_service),
    actor: Actor = Depends(get_actor),
):
    return StaffResponseSchema.model_validate(service.deactivate_staff(id, actor=actor))


# ---------------------------------------------------------------------------
# Assignments
# ---------------------------------------------------------------------------
@assignments_router.get("", response_model=List[StaffAssignmentResponseSchema], summary="List staff assignments")
def list_assignments(
    response: Response,
    staff_id: Optional[int] = Query(None, alias="staffId"),
    status: Optional[StaffAssignmentStatus] = Query(None),
    surgery_id: Optional[int] = Query(None, alias="surgeryId"),
    patient_id: Optional[int] = Query(None, alias="patientId"),
    pagination: PaginationParams = Depends(get_pagination),
    service: StaffService = Depends(get_staff_service),
):
    assignments = service.list_assignments(staff_id, status, surgery_id, patient_id, pagination.limit, pagination.offset)
    set_total_count(response, service.count_assignments(staff_id, status, surgery_id, patient_id))
    return [StaffAssignmentResponseSchema.model_validate(a) for a in assignments]


@assignments_router.get("/{id}", response_model=StaffAssignmentResponseSchema, summary="Get staff assignment")
def get_assignment(id: int, service: StaffService = Depends(get_staff_service)):
    assignment = service.get_assignment(id)
    if not assignment:
        raise NotFoundError(f"Staff assignment with id {id} not found")
    return StaffAssignmentResponseSchema.model_validate(assignment)


@assignments_router.post(
    "/{id}/release",
    response_model=StaffAssignmentReleaseResponseSchema,
    summary="Release assignment (staff -> AVAILABLE), then match the staff queue",
)
def release_assignment(
    id: int,
    payload: StaffAssignmentReleaseSchema = None,
    orchestrator: ReleaseOrchestrationService = Depends(get_release_orchestrator),
    actor: Actor = Depends(get_actor),
):
    payload = payload or StaffAssignmentReleaseSchema()
    outcome = orchestrator.release_assignment(id, payload.notes or "", actor, payload.auto_assign)
    return StaffAssignmentReleaseResponseSchema(
        assignment=StaffAssignmentResponseSchema.model_validate(outcome.resource),
        auto_assignment=auto_assignment_schema(outcome.auto_assignment) if outcome.auto_assignment else None,
    )
