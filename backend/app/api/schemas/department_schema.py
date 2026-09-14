from datetime import datetime
from typing import Optional
from pydantic import BaseModel, Field, ConfigDict


class DepartmentCreateSchema(BaseModel):
    name: str = Field(..., json_schema_extra={"example": "Intensive Care Unit"})
    code: str = Field(..., json_schema_extra={"example": "ICU"})


class DepartmentResponseSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    code: str
    total_beds: int
    occupied_beds: int
    created_at: Optional[datetime] = None
