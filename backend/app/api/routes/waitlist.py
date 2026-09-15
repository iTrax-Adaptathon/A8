from typing import List, Optional
from fastapi import APIRouter, Depends, Query, Response, status
from app.api.pagination import PaginationParams, get_pagination, set_total_count
from app.api.schemas import WaitlistCreateSchema, WaitlistResponseSchema
from app.application import WaitlistService
from app.core.dependencies import get_actor, get_waitlist_service
from app.domain.entities import Actor, WaitlistEntry
from app.domain.enums import WaitlistResourceType, WaitlistStatus
from app.domain.policies import NotFoundError, utc_now

router = APIRouter(prefix="/waitlist", tags=["Waitlist"])


@router.get(
    "",
    response_model=List[WaitlistResponseSchema],
    summary="List waitlist entries in deterministic queue order",
    description="Order: priority ASC (1 = most urgent), requestedAt ASC (longest waiting first), id ASC. "
    "The frontend must not re-order.",
)
def list_waitlist(
    response: Response,
    resource_type: Optional[WaitlistResourceType] = Query(None, alias="resourceType"),
    department_id: Optional[int] = Query(None, alias="departmentId"),
    status: Optional[WaitlistStatus] = Query(WaitlistStatus.WAITING, description="Default WAITING; pass empty for all"),
    patient_id: Optional[int] = Query(None, alias="patientId"),
    pagination: PaginationParams = Depends(get_pagination),
    service: WaitlistService = Depends(get_waitlist_service),
):
    entries = service.list_entries(resource_type, department_id, status, patient_id, pagination.limit, pagination.offset)
    set_total_count(response, service.count_entries(resource_type, department_id, status, patient_id))
    return [WaitlistResponseSchema.model_validate(e) for e in entries]


@router.get("/{id}", response_model=WaitlistResponseSchema, summary="Get waitlist entry")
def get_entry(id: int, service: WaitlistService = Depends(get_waitlist_service)):
    entry = service.get_entry(id)
    if not entry:
        raise NotFoundError(f"Waitlist entry with id {id} not found")
    return WaitlistResponseSchema.model_validate(entry)


@router.post("", response_model=WaitlistResponseSchema, status_code=status.HTTP_201_CREATED, summary="Add BED or STAFF waitlist entry")
def add_entry(
    payload: WaitlistCreateSchema,
    service: WaitlistService = Depends(get_waitlist_service),
    actor: Actor = Depends(get_actor),
):
    entry = WaitlistEntry(
        id=None,
        patient_id=payload.patient_id,
        resource_type=payload.resource_type,
        department_id=payload.department_id,
        priority=payload.priority,
        requested_at=utc_now(),
        reason=payload.reason or "",
        surgery_id=payload.surgery_id,
        required_bed_type=payload.required_bed_type,
        required_staff_role=payload.required_staff_role,
    )
    return WaitlistResponseSchema.model_validate(service.add_entry(entry, actor=actor))


@router.delete("/{id}", response_model=WaitlistResponseSchema, summary="Remove entry from queue (WAITING -> CANCELLED, record kept)")
def remove_entry(
    id: int,
    service: WaitlistService = Depends(get_waitlist_service),
    actor: Actor = Depends(get_actor),
):
    return WaitlistResponseSchema.model_validate(service.remove_entry(id, actor=actor))
