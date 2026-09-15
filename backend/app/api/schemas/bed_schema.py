from datetime import datetime
from typing import Optional
from pydantic import Field
from app.api.schemas.base import CamelModel
from app.api.schemas.match_schema import AutoAssignmentSchema
from app.domain.enums import BedStatus, BedType


class BedCreateSchema(CamelModel):
    bed_number: str = Field(..., min_length=1, json_schema_extra={"example": "ICU-BED-01"})
    bed_type: BedType = Field(default=BedType.ICU)
    department_id: int = Field(..., json_schema_extra={"example": 1})
    status: BedStatus = Field(
        default=BedStatus.AVAILABLE,
        description="Initial status. OCCUPIED is rejected (422): beds become occupied only through admission.",
    )


class BedStatusUpdateSchema(CamelModel):
    new_status: BedStatus = Field(
        ...,
        description="Target status. Allowed manual transitions: AVAILABLE<->CLEANING<->MAINTENANCE<->AVAILABLE. "
        "OCCUPIED beds cannot be changed here (409); OCCUPIED can never be set here (409).",
        json_schema_extra={"example": BedStatus.CLEANING},
    )
    notes: Optional[str] = Field(default="", json_schema_extra={"example": "Deep clean"})
    auto_assign: Optional[bool] = Field(
        default=None,
        description="When the bed becomes AVAILABLE: run deterministic matching (default: server setting).",
    )


class BedReleaseSchema(CamelModel):
    notes: Optional[str] = Field(default="Bed cleaned", json_schema_extra={"example": "Bed cleaned"})
    auto_assign: Optional[bool] = Field(
        default=None,
        description="Run deterministic matching after release (default: server setting AUTO_ASSIGN_ON_RELEASE).",
    )


class BedResponseSchema(CamelModel):
    id: int
    bed_number: str
    bed_type: BedType
    department_id: int
    status: BedStatus
    current_patient_id: Optional[int] = None
    is_active: bool = True
    created_at: Optional[datetime] = None


class BedReleaseResponseSchema(CamelModel):
    bed: BedResponseSchema
    auto_assignment: Optional[AutoAssignmentSchema] = None
