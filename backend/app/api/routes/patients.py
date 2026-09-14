from typing import List, Optional
from fastapi import APIRouter, Depends, Query, status, HTTPException
from app.api.schemas import (
    PatientCreateSchema,
    PatientAdmitSchema,
    PatientTransferSchema,
    PatientDischargeSchema,
    PatientResponseSchema,
)
from app.application import PatientService
from app.orchestration.flow_orchestration_service import FlowOrchestrationService
from app.core.dependencies import get_patient_service, get_flow_orchestrator
from app.domain.entities import Patient
from app.domain.enums import PatientStatus

router = APIRouter(prefix="/patients", tags=["Patients"])


@router.get("", response_model=List[PatientResponseSchema], summary="List patients")
def list_patients(
    status: Optional[PatientStatus] = Query(None, description="Filter by status"),
    department_id: Optional[int] = Query(None, description="Filter by department ID"),
    patient_service: PatientService = Depends(get_patient_service),
):
    patients = patient_service.list_patients(status=status, department_id=department_id)
    return [PatientResponseSchema.model_validate(p) for p in patients]


@router.get("/{id}", response_model=PatientResponseSchema, summary="Get patient details")
def get_patient(
    id: int,
    patient_service: PatientService = Depends(get_patient_service),
):
    patient = patient_service.get_patient(id)
    if not patient:
        raise HTTPException(status_code=404, detail=f"Patient {id} not found")
    return PatientResponseSchema.model_validate(patient)


@router.post("", response_model=PatientResponseSchema, status_code=status.HTTP_201_CREATED, summary="Create patient")
def create_patient(
    payload: PatientCreateSchema,
    patient_service: PatientService = Depends(get_patient_service),
):
    patient = Patient(
        id=None,
        name=payload.name,
        age=payload.age,
        gender=payload.gender,
        medical_record_number=payload.medical_record_number,
        current_status=PatientStatus.REGISTERED,
    )
    created = patient_service.create_patient(patient)
    return PatientResponseSchema.model_validate(created)


@router.post("/{id}/admit", response_model=PatientResponseSchema, summary="Admit patient")
def admit_patient(
    id: int,
    payload: PatientAdmitSchema,
    orchestrator: FlowOrchestrationService = Depends(get_flow_orchestrator),
):
    updated = orchestrator.admit_patient(
        patient_id=id,
        department_id=payload.department_id,
        bed_id=payload.bed_id,
        notes=payload.notes or "Patient admitted",
    )
    return PatientResponseSchema.model_validate(updated)


@router.post("/{id}/transfer", response_model=PatientResponseSchema, summary="Transfer patient")
def transfer_patient(
    id: int,
    payload: PatientTransferSchema,
    orchestrator: FlowOrchestrationService = Depends(get_flow_orchestrator),
):
    updated = orchestrator.transfer_patient(
        patient_id=id,
        target_department_id=payload.target_department_id,
        target_bed_id=payload.target_bed_id,
        notes=payload.notes or "Patient transferred",
    )
    return PatientResponseSchema.model_validate(updated)


@router.post("/{id}/discharge", response_model=PatientResponseSchema, summary="Discharge patient")
def discharge_patient(
    id: int,
    payload: PatientDischargeSchema,
    orchestrator: FlowOrchestrationService = Depends(get_flow_orchestrator),
):
    updated = orchestrator.discharge_patient(
        patient_id=id,
        notes=payload.notes or "Patient discharged",
    )
    return PatientResponseSchema.model_validate(updated)
