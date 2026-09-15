from typing import Optional

from fastapi import Depends, Header
from sqlalchemy.orm import Session

from app.infrastructure.database import get_db
from app.infrastructure.repositories import (
    PatientRepository,
    BedRepository,
    DepartmentRepository,
    FlowEventRepository,
    TheatreRepository,
    TheatreSlotRepository,
    SurgeryRepository,
    StaffRepository,
    StaffAssignmentRepository,
    WaitlistRepository,
)
from app.application import (
    PatientService,
    BedService,
    DepartmentService,
    CapacityIntelligenceService,
    TheatreService,
    SurgeryService,
    StaffService,
    WaitlistService,
    MatchingService,
)
from app.domain.entities import Actor
from app.orchestration.flow_orchestration_service import FlowOrchestrationService
from app.orchestration.release_orchestration_service import ReleaseOrchestrationService
from app.realtime.event_bus import event_bus


# ---------------------------------------------------------------------------
# Actor tracking (no authentication): X-Actor-ID / X-Actor-Name headers
# ---------------------------------------------------------------------------
def get_actor(
    x_actor_id: Optional[str] = Header(
        default=None, alias="X-Actor-ID", description="Identifier of the person/system performing the action"
    ),
    x_actor_name: Optional[str] = Header(
        default=None, alias="X-Actor-Name", description="Display name of the actor"
    ),
) -> Actor:
    actor_id = (x_actor_id or "").strip() or "system"
    actor_name = (x_actor_name or "").strip() or ("System" if actor_id == "system" else actor_id)
    return Actor(id=actor_id[:100], name=actor_name[:200])


# ---------------------------------------------------------------------------
# Repositories
# ---------------------------------------------------------------------------
def get_patient_repo(db: Session = Depends(get_db)) -> PatientRepository:
    return PatientRepository(db)


def get_bed_repo(db: Session = Depends(get_db)) -> BedRepository:
    return BedRepository(db)


def get_department_repo(db: Session = Depends(get_db)) -> DepartmentRepository:
    return DepartmentRepository(db)


def get_flow_event_repo(db: Session = Depends(get_db)) -> FlowEventRepository:
    return FlowEventRepository(db)


def get_theatre_repo(db: Session = Depends(get_db)) -> TheatreRepository:
    return TheatreRepository(db)


def get_slot_repo(db: Session = Depends(get_db)) -> TheatreSlotRepository:
    return TheatreSlotRepository(db)


def get_surgery_repo(db: Session = Depends(get_db)) -> SurgeryRepository:
    return SurgeryRepository(db)


def get_staff_repo(db: Session = Depends(get_db)) -> StaffRepository:
    return StaffRepository(db)


def get_assignment_repo(db: Session = Depends(get_db)) -> StaffAssignmentRepository:
    return StaffAssignmentRepository(db)


def get_waitlist_repo(db: Session = Depends(get_db)) -> WaitlistRepository:
    return WaitlistRepository(db)


# ---------------------------------------------------------------------------
# Services
# ---------------------------------------------------------------------------
def get_patient_service(
    repo: PatientRepository = Depends(get_patient_repo),
    flow_event_repo: FlowEventRepository = Depends(get_flow_event_repo),
) -> PatientService:
    return PatientService(repo, flow_event_repo, event_bus)


def get_bed_service(
    repo: BedRepository = Depends(get_bed_repo),
    department_repo: DepartmentRepository = Depends(get_department_repo),
    flow_event_repo: FlowEventRepository = Depends(get_flow_event_repo),
) -> BedService:
    return BedService(repo, department_repo, flow_event_repo, event_bus)


def get_department_service(
    repo: DepartmentRepository = Depends(get_department_repo),
    bed_repo: BedRepository = Depends(get_bed_repo),
    theatre_repo: TheatreRepository = Depends(get_theatre_repo),
    flow_event_repo: FlowEventRepository = Depends(get_flow_event_repo),
) -> DepartmentService:
    return DepartmentService(repo, bed_repo, theatre_repo, flow_event_repo, event_bus)


def get_capacity_service(
    bed_repo: BedRepository = Depends(get_bed_repo),
    department_repo: DepartmentRepository = Depends(get_department_repo),
    theatre_repo: TheatreRepository = Depends(get_theatre_repo),
    slot_repo: TheatreSlotRepository = Depends(get_slot_repo),
    staff_repo: StaffRepository = Depends(get_staff_repo),
    waitlist_repo: WaitlistRepository = Depends(get_waitlist_repo),
) -> CapacityIntelligenceService:
    return CapacityIntelligenceService(bed_repo, department_repo, theatre_repo, slot_repo, staff_repo, waitlist_repo)


def get_flow_orchestrator(
    patient_repo: PatientRepository = Depends(get_patient_repo),
    bed_repo: BedRepository = Depends(get_bed_repo),
    department_repo: DepartmentRepository = Depends(get_department_repo),
    flow_event_repo: FlowEventRepository = Depends(get_flow_event_repo),
    waitlist_repo: WaitlistRepository = Depends(get_waitlist_repo),
) -> FlowOrchestrationService:
    return FlowOrchestrationService(patient_repo, bed_repo, department_repo, flow_event_repo, waitlist_repo, event_bus)


def get_theatre_service(
    theatre_repo: TheatreRepository = Depends(get_theatre_repo),
    slot_repo: TheatreSlotRepository = Depends(get_slot_repo),
    department_repo: DepartmentRepository = Depends(get_department_repo),
    flow_event_repo: FlowEventRepository = Depends(get_flow_event_repo),
) -> TheatreService:
    return TheatreService(theatre_repo, slot_repo, department_repo, flow_event_repo, event_bus)


def get_staff_service(
    staff_repo: StaffRepository = Depends(get_staff_repo),
    assignment_repo: StaffAssignmentRepository = Depends(get_assignment_repo),
    department_repo: DepartmentRepository = Depends(get_department_repo),
    patient_repo: PatientRepository = Depends(get_patient_repo),
    surgery_repo: SurgeryRepository = Depends(get_surgery_repo),
    slot_repo: TheatreSlotRepository = Depends(get_slot_repo),
    waitlist_repo: WaitlistRepository = Depends(get_waitlist_repo),
    flow_event_repo: FlowEventRepository = Depends(get_flow_event_repo),
) -> StaffService:
    return StaffService(
        staff_repo, assignment_repo, department_repo, patient_repo, surgery_repo, slot_repo, waitlist_repo,
        flow_event_repo, event_bus,
    )


def get_surgery_service(
    surgery_repo: SurgeryRepository = Depends(get_surgery_repo),
    patient_repo: PatientRepository = Depends(get_patient_repo),
    department_repo: DepartmentRepository = Depends(get_department_repo),
    theatre_repo: TheatreRepository = Depends(get_theatre_repo),
    slot_repo: TheatreSlotRepository = Depends(get_slot_repo),
    assignment_repo: StaffAssignmentRepository = Depends(get_assignment_repo),
    waitlist_repo: WaitlistRepository = Depends(get_waitlist_repo),
    staff_service: StaffService = Depends(get_staff_service),
    flow_event_repo: FlowEventRepository = Depends(get_flow_event_repo),
) -> SurgeryService:
    return SurgeryService(
        surgery_repo, patient_repo, department_repo, theatre_repo, slot_repo, assignment_repo, waitlist_repo,
        staff_service, flow_event_repo, event_bus,
    )


def get_waitlist_service(
    waitlist_repo: WaitlistRepository = Depends(get_waitlist_repo),
    patient_repo: PatientRepository = Depends(get_patient_repo),
    department_repo: DepartmentRepository = Depends(get_department_repo),
    flow_event_repo: FlowEventRepository = Depends(get_flow_event_repo),
) -> WaitlistService:
    return WaitlistService(waitlist_repo, patient_repo, department_repo, flow_event_repo, event_bus)


def get_matching_service(
    flow: FlowOrchestrationService = Depends(get_flow_orchestrator),
    surgery_service: SurgeryService = Depends(get_surgery_service),
    staff_service: StaffService = Depends(get_staff_service),
    waitlist_repo: WaitlistRepository = Depends(get_waitlist_repo),
    flow_event_repo: FlowEventRepository = Depends(get_flow_event_repo),
) -> MatchingService:
    return MatchingService(flow, surgery_service, staff_service, waitlist_repo, flow_event_repo, event_bus)


def get_release_orchestrator(
    flow: FlowOrchestrationService = Depends(get_flow_orchestrator),
    bed_service: BedService = Depends(get_bed_service),
    theatre_service: TheatreService = Depends(get_theatre_service),
    surgery_service: SurgeryService = Depends(get_surgery_service),
    staff_service: StaffService = Depends(get_staff_service),
    matching: MatchingService = Depends(get_matching_service),
) -> ReleaseOrchestrationService:
    return ReleaseOrchestrationService(flow, bed_service, theatre_service, surgery_service, staff_service, matching)
