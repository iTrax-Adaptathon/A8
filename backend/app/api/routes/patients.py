from typing import List, Optional
from fastapi import APIRouter, Depends, Query, Response, status
from app.api.pagination import PaginationParams, get_pagination, set_total_count
from app.api.schemas import (
    PatientCreateSchema,
    PatientAdmitSchema,
    PatientTransferSchema,
    PatientDischargeSchema,
    PatientResponseSchema,
    FlowEventResponseSchema,
)
from app.application import PatientService
from app.orchestration.flow_orchestration_service import FlowOrchestrationService
from app.core.dependencies import get_actor, get_patient_service, get_flow_orchestrator
from app.domain.entities import Actor, Patient
from app.domain.enums import PatientStatus
from app.domain.policies import NotFoundError

router = APIRouter(prefix="/patients", tags=["Patients"])


@router.get("", response_model=List[PatientResponseSchema], summary="List patients")
def list_patients(
    response: Response,
    status: Optional[PatientStatus] = Query(None, description="Filter by status"),
    department_id: Optional[int] = Query(None, alias="departmentId", description="Filter by department ID"),
    pagination: PaginationParams = Depends(get_pagination),
    patient_service: PatientService = Depends(get_patient_service),
):
    patients = patient_service.list_patients(
        status=status, department_id=department_id, limit=pagination.limit, offset=pagination.offset
    )
    set_total_count(response, patient_service.count_patients(status=status, department_id=department_id))
    return [PatientResponseSchema.model_validate(p) for p in patients]


@router.get("/{id}", response_model=PatientResponseSchema, summary="Get patient details")
def get_patient(
    id: int,
    patient_service: PatientService = Depends(get_patient_service),
):
    patient = patient_service.get_patient(id)
    if not patient:
        raise NotFoundError(f"Patient with id {id} not found")
    return PatientResponseSchema.model_validate(patient)


@router.get(
    "/{id}/history",
    response_model=List[FlowEventResponseSchema],
    summary="Complete chronological patient timeline (oldest first) incl. actor information",
)
def get_patient_history(
    id: int,
    response: Response,
    pagination: PaginationParams = Depends(get_pagination),
    patient_service: PatientService = Depends(get_patient_service),
):
    events = patient_service.get_history(id, limit=pagination.limit, offset=pagination.offset)
    set_total_count(response, patient_service.count_history(id))
    return [FlowEventResponseSchema.model_validate(e) for e in events]


@router.post("", response_model=PatientResponseSchema, status_code=status.HTTP_201_CREATED, summary="Register patient")
def create_patient(
    payload: PatientCreateSchema,
    patient_service: PatientService = Depends(get_patient_service),
    actor: Actor = Depends(get_actor),
):
    patient = Patient(
        id=None,
        name=payload.name,
        age=payload.age,
        gender=payload.gender,
        medical_record_number=payload.medical_record_number,
        current_status=PatientStatus.REGISTERED,
    )
    created = patient_service.create_patient(patient, actor=actor)
    return PatientResponseSchema.model_validate(created)


@router.post("/{id}/admit", response_model=PatientResponseSchema, summary="Admit patient (REGISTERED -> ADMITTED, bed -> OCCUPIED)")
def admit_patient(
    id: int,
    payload: PatientAdmitSchema,
    orchestrator: FlowOrchestrationService = Depends(get_flow_orchestrator),
    actor: Actor = Depends(get_actor),
):
    updated = orchestrator.admit_patient(
        patient_id=id,
        department_id=payload.department_id,
        bed_id=payload.bed_id,
        notes=payload.notes or "Patient admitted",
        actor=actor,
    )
    return PatientResponseSchema.model_validate(updated)


@router.post("/{id}/transfer", response_model=PatientResponseSchema, summary="Transfer patient (old bed -> CLEANING, new bed -> OCCUPIED)")
def transfer_patient(
    id: int,
    payload: PatientTransferSchema,
    orchestrator: FlowOrchestrationService = Depends(get_flow_orchestrator),
    actor: Actor = Depends(get_actor),
):
    updated = orchestrator.transfer_patient(
        patient_id=id,
        target_department_id=payload.target_department_id,
        target_bed_id=payload.target_bed_id,
        notes=payload.notes or "Patient transferred",
        actor=actor,
    )
    return PatientResponseSchema.model_validate(updated)


@router.post("/{id}/discharge", response_model=PatientResponseSchema, summary="Discharge patient (bed -> CLEANING)")
def discharge_patient(
    id: int,
    payload: PatientDischargeSchema,
    orchestrator: FlowOrchestrationService = Depends(get_flow_orchestrator),
    actor: Actor = Depends(get_actor),
):
    updated = orchestrator.discharge_patient(
        patient_id=id,
        notes=payload.notes or "Patient discharged",
        actor=actor,
    )
    return PatientResponseSchema.model_validate(updated)
