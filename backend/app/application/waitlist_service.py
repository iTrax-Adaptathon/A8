"""Waitlist: the single queue for BED, THEATRE and STAFF requests.

Queue rule (WaitlistPolicy): priority ASC (1 = most urgent), requested_at ASC
(longest waiting first), id ASC. Ordering is applied in the repository query;
the frontend never needs to sort.
"""
from typing import List, Optional

from app.application.audit_service import AuditService, TransactionalService
from app.domain.entities import Actor, SYSTEM_ACTOR, WaitlistEntry
from app.domain.enums import (
    FlowEventType,
    ResourceType,
    WaitlistResourceType,
    WaitlistStatus,
)
from app.domain.policies import (
    ConflictError,
    DomainValidationError,
    NotFoundError,
    PatientPolicy,
    WaitlistPolicy,
    utc_now,
)
from app.infrastructure.repositories import (
    DepartmentRepository,
    FlowEventRepository,
    PatientRepository,
    WaitlistRepository,
)
from app.realtime.event_bus import EventBus


class WaitlistService(TransactionalService):
    def __init__(
        self,
        waitlist_repo: WaitlistRepository,
        patient_repo: Optional[PatientRepository] = None,
        department_repo: Optional[DepartmentRepository] = None,
        flow_event_repo: Optional[FlowEventRepository] = None,
        event_bus: Optional[EventBus] = None,
    ):
        db = waitlist_repo.db
        super().__init__(db, AuditService(flow_event_repo or FlowEventRepository(db)), event_bus)
        self.waitlist_repo = waitlist_repo
        self.patient_repo = patient_repo or PatientRepository(db)
        self.department_repo = department_repo or DepartmentRepository(db)

    def get_entry(self, entry_id: int) -> Optional[WaitlistEntry]:
        return self.waitlist_repo.get_by_id(entry_id)

    def list_entries(
        self,
        resource_type: Optional[WaitlistResourceType] = None,
        department_id: Optional[int] = None,
        status: Optional[WaitlistStatus] = None,
        patient_id: Optional[int] = None,
        limit: Optional[int] = None,
        offset: int = 0,
    ) -> List[WaitlistEntry]:
        return self.waitlist_repo.get_all(resource_type, department_id, status, patient_id, limit, offset)

    def count_entries(
        self,
        resource_type: Optional[WaitlistResourceType] = None,
        department_id: Optional[int] = None,
        status: Optional[WaitlistStatus] = None,
        patient_id: Optional[int] = None,
    ) -> int:
        return self.waitlist_repo.count(resource_type, department_id, status, patient_id)

    def add_entry(self, entry: WaitlistEntry, actor: Actor = SYSTEM_ACTOR) -> WaitlistEntry:
        WaitlistPolicy.validate_priority(entry.priority)
        if entry.resource_type == WaitlistResourceType.THEATRE:
            raise DomainValidationError(
                "THEATRE waitlist entries are created automatically when a surgery is created (POST /surgeries)."
            )
        if entry.resource_type == WaitlistResourceType.STAFF and entry.required_staff_role is None:
            raise DomainValidationError("requiredStaffRole is required for a STAFF waitlist entry")
        with self.transaction() as outbox:
            patient = self.patient_repo.get_by_id(entry.patient_id)
            if not patient:
                raise NotFoundError(f"Patient with id {entry.patient_id} not found")
            PatientPolicy.validate_active(patient)
            department = self.department_repo.get_by_id(entry.department_id)
            if not department:
                raise NotFoundError(f"Department with id {entry.department_id} not found")
            if not department.is_active:
                raise ConflictError(f"Department {department.name} is inactive")
            if entry.resource_type == WaitlistResourceType.BED and patient.current_department_id == entry.department_id \
                    and patient.current_bed_id is not None:
                raise ConflictError(f"Patient {patient.id} already has a bed in department {department.name}")
            existing = self.waitlist_repo.find_waiting_for_patient(entry.patient_id, entry.resource_type)
            if existing is not None:
                raise ConflictError(
                    f"Patient {entry.patient_id} is already waiting for a {entry.resource_type.value} (entry {existing.id})"
                )
            entry.status = WaitlistStatus.WAITING
            entry.requested_at = entry.requested_at or utc_now()
            created = self.waitlist_repo.create(entry)
            self.audit.record(
                FlowEventType.WAITLIST_ADDED,
                actor=actor,
                patient_id=created.patient_id,
                resource_type=ResourceType.WAITLIST_ENTRY,
                resource_id=created.id,
                department_id=created.department_id,
                new_state=WaitlistStatus.WAITING.value,
                notes=created.reason or f"Waiting for {created.resource_type.value}",
                metadata={"resourceType": created.resource_type.value, "priority": created.priority},
            )
            outbox.add("WAITLIST_UPDATED", ResourceType.WAITLIST_ENTRY, created.id, actor,
                       patient_id=created.patient_id, department_id=created.department_id,
                       new_state=WaitlistStatus.WAITING.value)
        return created

    def remove_entry(self, entry_id: int, notes: str = "", actor: Actor = SYSTEM_ACTOR) -> WaitlistEntry:
        """WAITING -> CANCELLED. The row is kept for history."""
        with self.transaction() as outbox:
            entry = self.waitlist_repo.get_by_id(entry_id)
            if not entry:
                raise NotFoundError(f"Waitlist entry with id {entry_id} not found")
            if entry.status != WaitlistStatus.WAITING:
                raise ConflictError(f"Waitlist entry {entry_id} is already {entry.status.value}")
            if not self.waitlist_repo.resolve_if_waiting(entry_id, WaitlistStatus.CANCELLED):
                raise ConflictError(f"Waitlist entry {entry_id} changed state during removal")
            self.audit.record(
                FlowEventType.WAITLIST_REMOVED,
                actor=actor,
                patient_id=entry.patient_id,
                resource_type=ResourceType.WAITLIST_ENTRY,
                resource_id=entry_id,
                department_id=entry.department_id,
                previous_state=WaitlistStatus.WAITING.value,
                new_state=WaitlistStatus.CANCELLED.value,
                notes=notes or "Removed from waitlist",
                metadata={"resourceType": entry.resource_type.value},
            )
            outbox.add("WAITLIST_UPDATED", ResourceType.WAITLIST_ENTRY, entry_id, actor,
                       patient_id=entry.patient_id, department_id=entry.department_id,
                       previous_state=WaitlistStatus.WAITING.value, new_state=WaitlistStatus.CANCELLED.value)
            updated = self.waitlist_repo.get_by_id(entry_id)
        return updated
