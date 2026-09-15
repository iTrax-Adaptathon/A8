from typing import List, Optional

from app.application.audit_service import AuditService, TransactionalService
from app.domain.entities import Actor, FlowEvent, Patient, SYSTEM_ACTOR
from app.domain.enums import FlowEventType, PatientStatus, ResourceType
from app.domain.policies import NotFoundError
from app.infrastructure.repositories import FlowEventRepository, PatientRepository
from app.realtime.event_bus import EventBus


class PatientService(TransactionalService):
    def __init__(
        self,
        patient_repo: PatientRepository,
        flow_event_repo: Optional[FlowEventRepository] = None,
        event_bus: Optional[EventBus] = None,
    ):
        db = patient_repo.db
        self.flow_event_repo = flow_event_repo or FlowEventRepository(db)
        super().__init__(db, AuditService(self.flow_event_repo), event_bus)
        self.patient_repo = patient_repo

    def create_patient(self, patient: Patient, actor: Actor = SYSTEM_ACTOR) -> Patient:
        with self.transaction() as outbox:
            created = self.patient_repo.create(patient)
            self.audit.record(
                FlowEventType.RESOURCE_CREATED,
                actor=actor,
                patient_id=created.id,
                resource_type=ResourceType.PATIENT,
                resource_id=created.id,
                new_state=created.current_status.value,
                notes=f"Patient {created.medical_record_number} registered",
            )
            outbox.add("PATIENT_UPDATED", ResourceType.PATIENT, created.id, actor,
                       patient_id=created.id, new_state=created.current_status.value)
        return created

    def get_patient(self, patient_id: int) -> Optional[Patient]:
        return self.patient_repo.get_by_id(patient_id)

    def list_patients(
        self,
        status: Optional[PatientStatus] = None,
        department_id: Optional[int] = None,
        limit: Optional[int] = None,
        offset: int = 0,
    ) -> List[Patient]:
        return self.patient_repo.get_all(status=status, department_id=department_id, limit=limit, offset=offset)

    def count_patients(self, status: Optional[PatientStatus] = None, department_id: Optional[int] = None) -> int:
        return self.patient_repo.count(status=status, department_id=department_id)

    def get_history(self, patient_id: int, limit: Optional[int] = None, offset: int = 0) -> List[FlowEvent]:
        """Complete chronological timeline (oldest first) including actor info."""
        if not self.patient_repo.get_by_id(patient_id):
            raise NotFoundError(f"Patient with id {patient_id} not found")
        return self.flow_event_repo.get_patient_history(patient_id, limit=limit, offset=offset)

    def count_history(self, patient_id: int) -> int:
        return self.flow_event_repo.count(patient_id=patient_id)
