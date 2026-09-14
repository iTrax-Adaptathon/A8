from fastapi import Depends
from sqlalchemy.orm import Session
from app.infrastructure.database import get_db
from app.infrastructure.repositories import (
    PatientRepository,
    BedRepository,
    DepartmentRepository,
    FlowEventRepository,
)
from app.application import (
    PatientService,
    BedService,
    DepartmentService,
    CapacityIntelligenceService,
)
from app.orchestration.flow_orchestration_service import FlowOrchestrationService


def get_patient_repo(db: Session = Depends(get_db)) -> PatientRepository:
    return PatientRepository(db)


def get_bed_repo(db: Session = Depends(get_db)) -> BedRepository:
    return BedRepository(db)


def get_department_repo(db: Session = Depends(get_db)) -> DepartmentRepository:
    return DepartmentRepository(db)


def get_flow_event_repo(db: Session = Depends(get_db)) -> FlowEventRepository:
    return FlowEventRepository(db)


def get_patient_service(repo: PatientRepository = Depends(get_patient_repo)) -> PatientService:
    return PatientService(repo)


def get_bed_service(repo: BedRepository = Depends(get_bed_repo)) -> BedService:
    return BedService(repo)


def get_department_service(repo: DepartmentRepository = Depends(get_department_repo)) -> DepartmentService:
    return DepartmentService(repo)


def get_capacity_service(
    bed_repo: BedRepository = Depends(get_bed_repo),
    department_repo: DepartmentRepository = Depends(get_department_repo),
) -> CapacityIntelligenceService:
    return CapacityIntelligenceService(bed_repo, department_repo)


def get_flow_orchestrator(
    patient_repo: PatientRepository = Depends(get_patient_repo),
    bed_repo: BedRepository = Depends(get_bed_repo),
    department_repo: DepartmentRepository = Depends(get_department_repo),
    flow_event_repo: FlowEventRepository = Depends(get_flow_event_repo),
) -> FlowOrchestrationService:
    return FlowOrchestrationService(patient_repo, bed_repo, department_repo, flow_event_repo)
