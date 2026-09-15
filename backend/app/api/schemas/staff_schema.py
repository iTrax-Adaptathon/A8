from datetime import datetime
from typing import List, Optional
from pydantic import Field
from app.api.schemas.base import CamelModel, UtcDateTime
from app.api.schemas.match_schema import AutoAssignmentSchema
from app.domain.enums import StaffAssignmentStatus, StaffAssignmentType, StaffRole, StaffStatus


class StaffCreateSchema(CamelModel):
    name: str = Field(..., min_length=1, json_schema_extra={"example": "Dr. Miranda Bailey"})
    role: StaffRole = Field(..., json_schema_extra={"example": "SURGEON"})
    department_id: int = Field(..., json_schema_extra={"example": 6})
    shift_start: UtcDateTime = Field(..., json_schema_extra={"example": "2026-09-16T07:00:00Z"})
    shift_end: UtcDateTime = Field(..., json_schema_extra={"example": "2026-09-16T19:00:00Z"})
    status: StaffStatus = Field(default=StaffStatus.AVAILABLE, description="ASSIGNED is rejected (409).")


class StaffStatusUpdateSchema(CamelModel):
    new_status: StaffStatus = Field(..., description="AVAILABLE <-> OFF_DUTY only; ASSIGNED is set by assignments.")
    notes: Optional[str] = ""
    auto_assign: Optional[bool] = None


class StaffAssignSchema(CamelModel):
    assignment_type: StaffAssignmentType = Field(..., json_schema_extra={"example": "SURGERY"})
    surgery_id: Optional[int] = Field(default=None, json_schema_extra={"example": 1})
    patient_id: Optional[int] = Field(default=None, json_schema_extra={"example": 1})
    required_role: Optional[StaffRole] = Field(
        default=None, description="Role the assignment demands (defaults to requiredStaffRole of the surgery)"
    )
    notes: Optional[str] = ""


class StaffAssignmentReleaseSchema(CamelModel):
    notes: Optional[str] = ""
    auto_assign: Optional[bool] = None


class StaffResponseSchema(CamelModel):
    id: int
    name: str
    role: StaffRole
    department_id: int
    shift_start: datetime
    shift_end: datetime
    status: StaffStatus
    is_active: bool = True
    created_at: Optional[datetime] = None


class StaffAssignmentResponseSchema(CamelModel):
    id: int
    staff_id: int
    assignment_type: StaffAssignmentType
    surgery_id: Optional[int] = None
    patient_id: Optional[int] = None
    department_id: int
    start_time: datetime
    end_time: Optional[datetime] = None
    status: StaffAssignmentStatus
    released_at: Optional[datetime] = None


class StaffActionResponseSchema(CamelModel):
    staff: StaffResponseSchema
    auto_assignment: Optional[AutoAssignmentSchema] = None


class StaffAssignmentReleaseResponseSchema(CamelModel):
    assignment: StaffAssignmentResponseSchema
    auto_assignment: Optional[AutoAssignmentSchema] = None
