from typing import List, Optional
from fastapi import APIRouter, Depends, Query, status, HTTPException
from app.api.schemas import BedCreateSchema, BedStatusUpdateSchema, BedResponseSchema
from app.application import BedService
from app.core.dependencies import get_bed_service
from app.domain.entities import Bed
from app.domain.enums import BedStatus, BedType

router = APIRouter(prefix="/beds", tags=["Beds"])


@router.get("", response_model=List[BedResponseSchema], summary="List beds")
def list_beds(
    department_id: Optional[int] = Query(None, description="Filter by department ID"),
    status: Optional[BedStatus] = Query(None, description="Filter by status"),
    bed_type: Optional[BedType] = Query(None, description="Filter by bed type"),
    bed_service: BedService = Depends(get_bed_service),
):
    beds = bed_service.list_beds(department_id=department_id, status=status, bed_type=bed_type)
    return [BedResponseSchema.model_validate(b) for b in beds]


@router.get("/available", response_model=List[BedResponseSchema], summary="List available beds")
def list_available_beds(
    department_id: Optional[int] = Query(None, description="Filter by department ID"),
    bed_service: BedService = Depends(get_bed_service),
):
    beds = bed_service.list_beds(department_id=department_id, status=BedStatus.AVAILABLE)
    return [BedResponseSchema.model_validate(b) for b in beds]


@router.get("/{id}", response_model=BedResponseSchema, summary="Get bed details")
def get_bed(
    id: int,
    bed_service: BedService = Depends(get_bed_service),
):
    bed = bed_service.get_bed(id)
    if not bed:
        raise HTTPException(status_code=404, detail=f"Bed {id} not found")
    return BedResponseSchema.model_validate(bed)


@router.post("", response_model=BedResponseSchema, status_code=status.HTTP_201_CREATED, summary="Create bed")
def create_bed(
    payload: BedCreateSchema,
    bed_service: BedService = Depends(get_bed_service),
):
    bed = Bed(
        id=None,
        bed_number=payload.bed_number,
        bed_type=payload.bed_type,
        department_id=payload.department_id,
        status=payload.status,
    )
    created = bed_service.create_bed(bed)
    return BedResponseSchema.model_validate(created)


@router.patch("/{id}/status", response_model=BedResponseSchema, summary="Update bed status")
def update_bed_status(
    id: int,
    payload: BedStatusUpdateSchema,
    bed_service: BedService = Depends(get_bed_service),
):
    updated = bed_service.update_bed_status(id, payload.new_status)
    return BedResponseSchema.model_validate(updated)
