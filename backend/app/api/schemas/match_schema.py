from datetime import datetime
from typing import Any, Dict, List, Optional
from pydantic import Field
from app.api.schemas.base import CamelModel
from app.domain.enums import ResourceType


class AutoAssignmentSchema(CamelModel):
    """Outcome of one deterministic auto-assignment attempt after a release."""

    resource_type: ResourceType
    resource_id: int
    matched: bool
    waitlist_entry_id: Optional[int] = None
    patient_id: Optional[int] = None
    surgery_id: Optional[int] = None
    reason: Optional[str] = None
    candidates_evaluated: int = 0
    rejections: List[Dict[str, Any]] = []


class MatchCandidateSchema(CamelModel):
    rank: int = Field(..., description="1 = first in the deterministic queue order")
    waitlist_entry_id: int
    patient_id: int
    surgery_id: Optional[int] = None
    priority: int
    requested_at: datetime
    reason: str


class MatchResultSchema(CamelModel):
    """Read-only match computation (nothing is written)."""

    resource_type: ResourceType
    resource_id: int
    resource_available: bool = Field(..., description="False when the resource itself is not assignable right now")
    department_id: Optional[int] = None
    candidates: List[MatchCandidateSchema]


class MatchConfirmSchema(CamelModel):
    resource_type: ResourceType = Field(..., description="BED, THEATRE_SLOT or STAFF")
    resource_id: int
    waitlist_entry_id: int
    notes: Optional[str] = Field(default="", json_schema_extra={"example": "Confirmed by bed manager"})
