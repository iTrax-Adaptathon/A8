from datetime import datetime
from typing import List, Optional
from pydantic import Field
from app.api.schemas.base import CamelModel
from app.api.schemas.match_schema import AutoAssignmentSchema
from app.domain.enums import StaffRole, SurgeryStatus


class SurgeryCreateSchema(CamelModel):
    patient_id: int = Field(..., json_schema_extra={"example": 1})
    department_id: int = Field(..., json_schema_extra={"example": 6})
    procedure_name: str = Field(..., min_length=1, json_schema_extra={"example": "Appendectomy"})
    duration_minutes: int = Field(..., ge=15, le=1440, json_schema_extra={"example": 90})
    priority: int = Field(default=3, ge=1, le=5, description="1 = most urgent, 5 = elective")
    required_staff_role: Optional[StaffRole] = Field(default=None, json_schema_extra={"example": "SURGEON"})
    reason: Optional[str] = Field(default="", description="Waiting reason recorded on the theatre queue entry")


class SurgeryScheduleSchema(CamelModel):
    slot_id: int = Field(..., json_schema_extra={"example": 3})
    notes: Optional[str] = ""


class SurgeryActionSchema(CamelModel):
    notes: Optional[str] = ""
    auto_assign: Optional[bool] = Field(default=None, description="Re-match freed slot/staff (default: server setting)")


class SurgeryResponseSchema(CamelModel):
    id: int
    patient_id: int
    department_id: int
    procedure_name: str
    duration_minutes: int
    priority: int
    status: SurgeryStatus
    theatre_id: Optional[int] = None
    slot_id: Optional[int] = None
    required_staff_role: Optional[StaffRole] = None
    created_at: Optional[datetime] = None
    scheduled_at: Optional[datetime] = None
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None


class SurgeryActionResponseSchema(CamelModel):
    surgery: SurgeryResponseSchema
    auto_assignments: List[AutoAssignmentSchema] = []
