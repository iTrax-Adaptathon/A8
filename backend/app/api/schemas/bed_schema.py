from datetime import datetime
from typing import Optional
from pydantic import BaseModel, Field, ConfigDict
from app.domain.enums import BedStatus, BedType


class BedCreateSchema(BaseModel):
    bed_number: str = Field(..., json_schema_extra={"example": "ICU-BED-01"})
    bed_type: BedType = Field(default=BedType.ICU)
    department_id: int = Field(..., json_schema_extra={"example": 1})
    status: BedStatus = Field(default=BedStatus.AVAILABLE)


class BedStatusUpdateSchema(BaseModel):
    new_status: BedStatus = Field(..., json_schema_extra={"example": BedStatus.CLEANING})


class BedResponseSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    bed_number: str
    bed_type: BedType
    department_id: int
    status: BedStatus
    current_patient_id: Optional[int] = None
    created_at: Optional[datetime] = None
