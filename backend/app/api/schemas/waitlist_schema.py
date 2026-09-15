from datetime import datetime
from typing import Optional
from pydantic import Field
from app.api.schemas.base import CamelModel
from app.domain.enums import BedType, StaffRole, WaitlistResourceType, WaitlistStatus


class WaitlistCreateSchema(CamelModel):
    patient_id: int = Field(..., json_schema_extra={"example": 5})
    resource_type: WaitlistResourceType = Field(
        ..., description="BED or STAFF. THEATRE entries are created automatically by POST /surgeries."
    )
    department_id: int = Field(..., json_schema_extra={"example": 2})
    priority: int = Field(default=3, ge=1, le=5, description="1 = most urgent, 5 = lowest")
    reason: Optional[str] = Field(default="", json_schema_extra={"example": "Awaiting ICU bed after triage"})
    required_bed_type: Optional[BedType] = Field(default=None, description="BED requests only")
    required_staff_role: Optional[StaffRole] = Field(default=None, description="STAFF requests: mandatory")
    surgery_id: Optional[int] = Field(default=None, description="STAFF requests tied to a surgery")


class WaitlistResponseSchema(CamelModel):
    id: int
    patient_id: int
    resource_type: WaitlistResourceType
    department_id: int
    priority: int
    requested_at: datetime
    status: WaitlistStatus
    reason: str = ""
    surgery_id: Optional[int] = None
    required_bed_type: Optional[BedType] = None
    required_staff_role: Optional[StaffRole] = None
    fulfilled_at: Optional[datetime] = None
    fulfilled_resource_id: Optional[int] = None
