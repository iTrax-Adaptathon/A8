from datetime import datetime
from typing import List, Optional
from pydantic import Field
from app.api.schemas.base import CamelModel, UtcDateTime
from app.api.schemas.match_schema import AutoAssignmentSchema
from app.domain.enums import TheatreSlotStatus, TheatreStatus


class TheatreCreateSchema(CamelModel):
    name: str = Field(..., min_length=1, json_schema_extra={"example": "Theatre 1"})
    department_id: int = Field(..., json_schema_extra={"example": 6})
    status: TheatreStatus = Field(default=TheatreStatus.AVAILABLE, description="IN_USE is rejected (409).")


class TheatreStatusUpdateSchema(CamelModel):
    new_status: TheatreStatus = Field(
        ...,
        description="Manual transitions: AVAILABLE->UNAVAILABLE|CLEANING, CLEANING->AVAILABLE|UNAVAILABLE, "
        "UNAVAILABLE->AVAILABLE. IN_USE is controlled by surgeries.",
    )
    notes: Optional[str] = ""
    auto_assign: Optional[bool] = None


class TheatreReleaseSchema(CamelModel):
    notes: Optional[str] = Field(default="Theatre cleaned")
    auto_assign: Optional[bool] = Field(default=None, description="Match waiting surgeries into the AVAILABLE slots of this theatre.")


class TheatreResponseSchema(CamelModel):
    id: int
    name: str
    department_id: int
    status: TheatreStatus
    is_active: bool = True
    created_at: Optional[datetime] = None


class TheatreReleaseResponseSchema(CamelModel):
    theatre: TheatreResponseSchema
    auto_assignments: List[AutoAssignmentSchema] = []


class TheatreSlotCreateSchema(CamelModel):
    theatre_id: int = Field(..., json_schema_extra={"example": 1})
    start_time: UtcDateTime = Field(..., json_schema_extra={"example": "2026-09-16T08:00:00Z"})
    end_time: UtcDateTime = Field(..., json_schema_extra={"example": "2026-09-16T10:00:00Z"})
    auto_assign: Optional[bool] = Field(default=None, description="Match a waiting surgery into the new slot immediately.")


class TheatreSlotCancelSchema(CamelModel):
    notes: Optional[str] = ""


class TheatreSlotResponseSchema(CamelModel):
    id: int
    theatre_id: int
    start_time: datetime
    end_time: datetime
    duration_minutes: int
    status: TheatreSlotStatus
    surgery_id: Optional[int] = None
    created_at: Optional[datetime] = None


class TheatreSlotCreateResponseSchema(CamelModel):
    slot: TheatreSlotResponseSchema
    auto_assignment: Optional[AutoAssignmentSchema] = None
