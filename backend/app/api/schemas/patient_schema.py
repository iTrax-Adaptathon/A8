from datetime import datetime
from typing import Optional
from pydantic import BaseModel, Field, ConfigDict
from app.domain.enums import PatientStatus


class PatientCreateSchema(BaseModel):
    name: str = Field(..., json_schema_extra={"example": "Sarah Connor"})
    age: int = Field(..., ge=0, json_schema_extra={"example": 42})
    gender: str = Field(..., json_schema_extra={"example": "Female"})
    medical_record_number: str = Field(..., json_schema_extra={"example": "MRN-100293"})


class PatientAdmitSchema(BaseModel):
    department_id: int = Field(..., json_schema_extra={"example": 1})
    bed_id: int = Field(..., json_schema_extra={"example": 5})
    notes: Optional[str] = Field(default="Patient admitted", json_schema_extra={"example": "Admitted via ER"})


class PatientTransferSchema(BaseModel):
    target_department_id: int = Field(..., json_schema_extra={"example": 2})
    target_bed_id: int = Field(..., json_schema_extra={"example": 12})
    notes: Optional[str] = Field(default="Patient transferred", json_schema_extra={"example": "Transferred to ICU"})


class PatientDischargeSchema(BaseModel):
    notes: Optional[str] = Field(default="Patient discharged", json_schema_extra={"example": "Recovered"})


class PatientResponseSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)

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
