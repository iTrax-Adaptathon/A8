from datetime import datetime
from typing import Optional
from pydantic import Field
from app.api.schemas.base import CamelModel
from app.domain.enums import PatientStatus


class PatientCreateSchema(CamelModel):
    name: str = Field(..., min_length=1, json_schema_extra={"example": "Sarah Connor"})
    age: int = Field(..., ge=0, le=130, json_schema_extra={"example": 42})
    gender: str = Field(..., min_length=1, json_schema_extra={"example": "Female"})
    medical_record_number: str = Field(..., min_length=1, json_schema_extra={"example": "MRN-100293"})


class PatientAdmitSchema(CamelModel):
    department_id: int = Field(..., json_schema_extra={"example": 1})
    bed_id: int = Field(..., json_schema_extra={"example": 5})
    notes: Optional[str] = Field(default="Patient admitted", json_schema_extra={"example": "Admitted via ER"})


class PatientTransferSchema(CamelModel):
    target_department_id: int = Field(..., json_schema_extra={"example": 2})
    target_bed_id: int = Field(..., json_schema_extra={"example": 12})
    notes: Optional[str] = Field(default="Patient transferred", json_schema_extra={"example": "Transferred to ICU"})


class PatientDischargeSchema(CamelModel):
    notes: Optional[str] = Field(default="Patient discharged", json_schema_extra={"example": "Recovered"})


class PatientResponseSchema(CamelModel):
    id: int
    name: str
    age: int
    gender: str
    medical_record_number: str
    current_status: PatientStatus
    current_department_id: Optional[int] = None
    current_bed_id: Optional[int] = None
    admitted_at: Optional[datetime] = None
    discharged_at: Optional[datetime] = None
    created_at: Optional[datetime] = None
