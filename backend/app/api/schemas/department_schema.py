from datetime import datetime
from typing import Optional
from pydantic import Field
from app.api.schemas.base import CamelModel


class DepartmentCreateSchema(CamelModel):
    name: str = Field(..., min_length=1, json_schema_extra={"example": "Intensive Care Unit"})
    code: str = Field(..., min_length=1, json_schema_extra={"example": "ICU"})


class DepartmentResponseSchema(CamelModel):
    id: int
    name: str
    code: str
    total_beds: int
    occupied_beds: int
    is_active: bool = True
    created_at: Optional[datetime] = None
