"""Surgery lifecycle: WAITING -> SCHEDULED -> IN_PROGRESS -> COMPLETED (or CANCELLED).

* Creating a surgery adds a THEATRE entry to the waitlist (the single queue).
* Scheduling targets one specific AVAILABLE slot whose parent theatre is
  active and AVAILABLE, and claims it atomically (one slot -> one surgery).
* Starting a surgery puts its theatre IN_USE and requires the required staff
  role (if any) to be actively assigned.
* Completing marks the slot COMPLETED, puts the theatre into CLEANING and
  releases all active staff assignments for the surgery.
"""
from typing import List, Optional

from app.application.audit_service import AuditService, Outbox, TransactionalService
from app.application.staff_service import StaffService
from app.domain.entities import Actor, SYSTEM_ACTOR, Surgery, WaitlistEntry
from app.domain.enums import (
    EventSource,
    FlowEventType,
    ResourceType,
    SurgeryStatus,
    TheatreSlotStatus,
    TheatreStatus,
    WaitlistResourceType,
    WaitlistStatus,
)
from app.domain.policies import (
    ConflictError,
    NotFoundError,
    PatientPolicy,
    SurgeryPolicy,
    WaitlistPolicy,
    utc_now,
)
from app.infrastructure.repositories import (
    DepartmentRepository,
    FlowEventRepository,
    PatientRepository,
    StaffAssignmentRepository,
    StaffRepository,
    SurgeryRepository,
    TheatreRepository,
    TheatreSlotRepository,
    WaitlistRepository,
)
from app.realtime.event_bus import EventBus


class SurgeryService(TransactionalService):
    def __init__(
        self,
        surgery_repo: SurgeryRepository,
        patient_repo: Optional[PatientRepository] = None,
        department_repo: Optional[DepartmentRepository] = None,
        theatre_repo: Optional[TheatreRepository] = None,
        slot_repo: Optional[TheatreSlotRepository] = None,
        assignment_repo: Optional[StaffAssignmentRepository] = None,
        waitlist_repo: Optional[WaitlistRepository] = None,
        staff_service: Optional[StaffService] = None,
        flow_event_repo: Optional[FlowEventRepository] = None,
        event_bus: Optional[EventBus] = None,
    ):
        db = surgery_repo.db
        audit = AuditService(flow_event_repo or FlowEventRepository(db))
        super().__init__(db, audit, event_bus)
        self.surgery_repo = surgery_repo
        self.patient_repo = patient_repo or PatientRepository(db)
        self.department_repo = department_repo or DepartmentRepository(db)
        self.theatre_repo = theatre_repo or TheatreRepository(db)
        self.slot_repo = slot_repo or TheatreSlotRepository(db)
        self.assignment_repo = assignment_repo or StaffAssignmentRepository(db)
        self.waitlist_repo = waitlist_repo or WaitlistRepository(db)
        self.staff_service = staff_service or StaffService(
            StaffRepository(db),
            assignment_repo=self.assignment_repo,
            flow_event_repo=audit.flow_event_repo,
            event_bus=self.event_bus,
        )

    # ------------------------------------------------------------------
    def get_surgery(self, surgery_id: int) -> Optional[Surgery]:
        return self.surgery_repo.get_by_id(surgery_id)

    def _require_surgery(self, surgery_id: int) -> Surgery:
        surgery = self.surgery_repo.get_by_id(surgery_id)
        if not surgery:
            raise NotFoundError(f"Surgery with id {surgery_id} not found")
        return surgery

    def list_surgeries(
        self,
        status: Optional[SurgeryStatus] = None,
        department_id: Optional[int] = None,
        patient_id: Optional[int] = None,
        theatre_id: Optional[int] = None,
        limit: Optional[int] = None,
        offset: int = 0,
    ) -> List[Surgery]:
        return self.surgery_repo.get_all(status, department_id, patient_id, theatre_id, limit, offset)

    def count_surgeries(
        self,
        status: Optional[SurgeryStatus] = None,
        department_id: Optional[int] = None,
        patient_id: Optional[int] = None,
        theatre_id: Optional[int] = None,
    ) -> int:
        return self.surgery_repo.count(status, department_id, patient_id, theatre_id)

    # ------------------------------------------------------------------
    def create_surgery(self, surgery: Surgery, reason: str = "", actor: Actor = SYSTEM_ACTOR) -> Surgery:
        SurgeryPolicy.validate_definition(surgery.duration_minutes, surgery.priority)
        with self.transaction() as outbox:
            patient = self.patient_repo.get_by_id(surgery.patient_id)
            if not patient:
                raise NotFoundError(f"Patient with id {surgery.patient_id} not found")
            PatientPolicy.validate_active(patient)
            department = self.department_repo.get_by_id(surgery.department_id)
            if not department:
                raise NotFoundError(f"Department with id {surgery.department_id} not found")
            if not department.is_active:
                raise ConflictError(f"Department {department.name} is inactive")

            surgery.status = SurgeryStatus.WAITING
            surgery.theatre_id = None
            surgery.slot_id = None
            created = self.surgery_repo.create(surgery)
            now = created.created_at or utc_now()
            entry = self.waitlist_repo.create(
                WaitlistEntry(
                    id=None,
                    patient_id=created.patient_id,
                    resource_type=WaitlistResourceType.THEATRE,
                    department_id=created.department_id,
                    priority=created.priority,
                    requested_at=now,
                    reason=reason or f"Theatre slot for {created.procedure_name}",
                    surgery_id=created.id,
                )
            )
            self.audit.record(
                FlowEventType.SURGERY_CREATED,
                actor=actor,
                patient_id=created.patient_id,
                resource_type=ResourceType.SURGERY,
                resource_id=created.id,
                department_id=created.department_id,
                new_state=SurgeryStatus.WAITING.value,
                notes=f"Surgery '{created.procedure_name}' created (priority {created.priority})",
                metadata={"waitlistEntryId": entry.id, "durationMinutes": created.duration_minutes},
            )
            self.audit.record(
                FlowEventType.WAITLIST_ADDED,
                actor=actor,
                patient_id=created.patient_id,
                resource_type=ResourceType.WAITLIST_ENTRY,
                resource_id=entry.id,
                department_id=created.department_id,
                new_state=WaitlistStatus.WAITING.value,
                notes=entry.reason,
                metadata={"resourceType": WaitlistResourceType.THEATRE.value, "surgeryId": created.id},
            )
            outbox.add("SURGERY_UPDATED", ResourceType.SURGERY, created.id, actor,
                       patient_id=created.patient_id, department_id=created.department_id,
                       new_state=SurgeryStatus.WAITING.value)
            outbox.add("WAITLIST_UPDATED", ResourceType.WAITLIST_ENTRY, entry.id, actor,
                       patient_id=created.patient_id, department_id=created.department_id,
                       new_state=WaitlistStatus.WAITING.value)
        return created

    # ------------------------------------------------------------------
    def schedule_surgery(
        self,
        surgery_id: int,
        slot_id: int,
        notes: str = "",
        actor: Actor = SYSTEM_ACTOR,
        source: EventSource = EventSource.MANUAL,
    ) -> Surgery:
        """The single validated booking workflow (used by manual calls AND matching)."""
        with self.transaction() as outbox:
            surgery = self._require_surgery(surgery_id)
            slot = self.slot_repo.get_by_id(slot_id)
            if not slot:
                raise NotFoundError(f"Theatre slot with id {slot_id} not found")
            theatre = self.theatre_repo.get_by_id(slot.theatre_id)
            if not theatre:
                raise NotFoundError(f"Theatre with id {slot.theatre_id} not found")
            patient = self.patient_repo.get_by_id(surgery.patient_id)
            if not patient:
                raise NotFoundError(f"Patient with id {surgery.patient_id} not found")

            SurgeryPolicy.validate_schedulable(surgery, patient, theatre, slot)
            now = utc_now()

            # 1. Atomic slot claim (one slot -> one surgery).
            if not self.slot_repo.book_if_available(slot_id, surgery_id):
                raise ConflictError(f"Theatre slot {slot_id} was booked by another operation")
            # 2. Atomic surgery transition (one surgery -> one slot).
            if not self.surgery_repo.set_status_if(
                surgery_id, SurgeryStatus.WAITING, SurgeryStatus.SCHEDULED,
                theatre_id=theatre.id, slot_id=slot_id, scheduled_at=now,
            ):
                raise ConflictError(f"Surgery {surgery_id} was modified by another operation")

            # 3. Queue entry fulfilled
            self._resolve_theatre_entry(surgery, WaitlistStatus.FULFILLED, slot_id, actor, source, outbox,
                                        f"Booked into theatre {theatre.name}")

            self.audit.record(
                FlowEventType.SURGERY_SCHEDULED,
                actor=actor,
                source=source,
                patient_id=surgery.patient_id,
                resource_type=ResourceType.SURGERY,
                resource_id=surgery_id,
                department_id=surgery.department_id,
                previous_state=SurgeryStatus.WAITING.value,
                new_state=SurgeryStatus.SCHEDULED.value,
                notes=notes or f"Scheduled in theatre {theatre.name}",
                metadata={"theatreId": theatre.id, "slotId": slot_id, "slotStart": slot.start_time.isoformat()},
            )
            self.audit.record(
                FlowEventType.THEATRE_SLOT_BOOKED,
                actor=actor,
                source=source,
                patient_id=surgery.patient_id,
                resource_type=ResourceType.THEATRE_SLOT,
                resource_id=slot_id,
                department_id=theatre.department_id,
                previous_state=TheatreSlotStatus.AVAILABLE.value,
                new_state=TheatreSlotStatus.BOOKED.value,
                notes=f"Booked by surgery {surgery_id}",
                metadata={"theatreId": theatre.id, "surgeryId": surgery_id},
            )
            outbox.add("SURGERY_UPDATED", ResourceType.SURGERY, surgery_id, actor, source,
                       patient_id=surgery.patient_id, department_id=surgery.department_id,
                       previous_state=SurgeryStatus.WAITING.value, new_state=SurgeryStatus.SCHEDULED.value)
            outbox.add("THEATRE_SLOT_UPDATED", ResourceType.THEATRE_SLOT, slot_id, actor, source,
                       patient_id=surgery.patient_id, department_id=theatre.department_id,
                       previous_state=TheatreSlotStatus.AVAILABLE.value, new_state=TheatreSlotStatus.BOOKED.value)
            updated = self._require_surgery(surgery_id)
        return updated

    def _resolve_theatre_entry(self, surgery: Surgery, new_status: WaitlistStatus, resource_id, actor, source, outbox: Outbox, note: str):
        entry = self.waitlist_repo.find_waiting_for_patient(surgery.patient_id, WaitlistResourceType.THEATRE, surgery.id)
        if entry is None:
            return
        fulfilled_at = utc_now() if new_status == WaitlistStatus.FULFILLED else None
        if self.waitlist_repo.resolve_if_waiting(entry.id, new_status, fulfilled_at, resource_id):
            event_type = FlowEventType.WAITLIST_FULFILLED if new_status == WaitlistStatus.FULFILLED else FlowEventType.WAITLIST_REMOVED
            self.audit.record(
                event_type, actor=actor, source=source, patient_id=surgery.patient_id,
                resource_type=ResourceType.WAITLIST_ENTRY, resource_id=entry.id, department_id=entry.department_id,
                previous_state=WaitlistStatus.WAITING.value, new_state=new_status.value, notes=note,
                metadata={"surgeryId": surgery.id, "slotId": resource_id},
            )
            outbox.add("WAITLIST_UPDATED", ResourceType.WAITLIST_ENTRY, entry.id, actor, source,
                       patient_id=surgery.patient_id, department_id=entry.department_id,
                       previous_state=WaitlistStatus.WAITING.value, new_state=new_status.value)

    def _requeue(self, surgery: Surgery, actor, source, outbox: Outbox, note: str) -> WaitlistEntry:
        """SCHEDULED -> WAITING puts the surgery back on the theatre queue with a
        fresh requested_at (its original wait was already honoured)."""
        entry = self.waitlist_repo.create(
            WaitlistEntry(
                id=None,
                patient_id=surgery.patient_id,
                resource_type=WaitlistResourceType.THEATRE,
                department_id=surgery.department_id,
                priority=surgery.priority,
                requested_at=utc_now(),
                reason=note,
                surgery_id=surgery.id,
            )
        )
        self.audit.record(
            FlowEventType.WAITLIST_ADDED, actor=actor, source=source, patient_id=surgery.patient_id,
            resource_type=ResourceType.WAITLIST_ENTRY, resource_id=entry.id, department_id=surgery.department_id,
            new_state=WaitlistStatus.WAITING.value, notes=note,
            metadata={"resourceType": WaitlistResourceType.THEATRE.value, "surgeryId": surgery.id},
        )
        outbox.add("WAITLIST_UPDATED", ResourceType.WAITLIST_ENTRY, entry.id, actor, source,
                   patient_id=surgery.patient_id, department_id=surgery.department_id,
                   new_state=WaitlistStatus.WAITING.value)
        return entry

    def _release_slot(self, surgery: Surgery, event_type: FlowEventType, actor, source, outbox: Outbox, note: str) -> Optional[int]:
        """BOOKED -> AVAILABLE for the surgery's slot. Returns the slot id."""
        if surgery.slot_id is None:
            return None
        slot = self.slot_repo.get_by_id(surgery.slot_id)
        theatre = self.theatre_repo.get_by_id(surgery.theatre_id) if surgery.theatre_id else None
        if slot and slot.status == TheatreSlotStatus.BOOKED:
            if not self.slot_repo.release_booking(slot.id, surgery.id):
                raise ConflictError(f"Theatre slot {slot.id} changed state during release")
            self.audit.record(
                event_type, actor=actor, source=source, patient_id=surgery.patient_id,
                resource_type=ResourceType.THEATRE_SLOT, resource_id=slot.id,
                department_id=theatre.department_id if theatre else surgery.department_id,
                previous_state=TheatreSlotStatus.BOOKED.value, new_state=TheatreSlotStatus.AVAILABLE.value,
                notes=note, metadata={"theatreId": slot.theatre_id, "surgeryId": surgery.id},
            )
            outbox.add("THEATRE_SLOT_UPDATED", ResourceType.THEATRE_SLOT, slot.id, actor, source,
                       patient_id=surgery.patient_id,
                       department_id=theatre.department_id if theatre else surgery.department_id,
                       previous_state=TheatreSlotStatus.BOOKED.value, new_state=TheatreSlotStatus.AVAILABLE.value)
            return slot.id
        return None

    def unschedule_surgery(self, surgery_id: int, notes: str = "", actor: Actor = SYSTEM_ACTOR) -> Surgery:
        """SCHEDULED -> WAITING; releases the slot (BOOKED -> AVAILABLE) and re-queues."""
        with self.transaction() as outbox:
            surgery = self._require_surgery(surgery_id)
            SurgeryPolicy.validate_transition(surgery.status, SurgeryStatus.WAITING)
            self._release_slot(surgery, FlowEventType.THEATRE_SLOT_RELEASED, actor, EventSource.MANUAL, outbox,
                               notes or "Surgery unscheduled")
            if not self.surgery_repo.set_status_if(
                surgery_id, SurgeryStatus.SCHEDULED, SurgeryStatus.WAITING, theatre_id=None, slot_id=None, scheduled_at=None
            ):
                raise ConflictError(f"Surgery {surgery_id} was modified by another operation")
            self._requeue(surgery, actor, EventSource.MANUAL, outbox, notes or "Surgery unscheduled; back on queue")
            self.audit.record(
                FlowEventType.SURGERY_UNSCHEDULED, actor=actor, patient_id=surgery.patient_id,
                resource_type=ResourceType.SURGERY, resource_id=surgery_id, department_id=surgery.department_id,
                previous_state=SurgeryStatus.SCHEDULED.value, new_state=SurgeryStatus.WAITING.value,
                notes=notes or "Surgery unscheduled", metadata={"slotId": surgery.slot_id},
            )
            outbox.add("SURGERY_UPDATED", ResourceType.SURGERY, surgery_id, actor,
                       patient_id=surgery.patient_id, department_id=surgery.department_id,
                       previous_state=SurgeryStatus.SCHEDULED.value, new_state=SurgeryStatus.WAITING.value)
            updated = self._require_surgery(surgery_id)
        return updated

    def start_surgery(self, surgery_id: int, notes: str = "", actor: Actor = SYSTEM_ACTOR) -> Surgery:
        with self.transaction() as outbox:
            surgery = self._require_surgery(surgery_id)
            SurgeryPolicy.validate_transition(surgery.status, SurgeryStatus.IN_PROGRESS)
            if surgery.slot_id is None or surgery.theatre_id is None:
                raise ConflictError(f"Surgery {surgery_id} has no theatre slot")
            theatre = self.theatre_repo.get_by_id(surgery.theatre_id)
            if not theatre or not theatre.is_active:
                raise ConflictError(f"Theatre {surgery.theatre_id} is not active")
            if theatre.status != TheatreStatus.AVAILABLE:
                raise ConflictError(f"Theatre {theatre.name} is '{theatre.status.value}'; surgery cannot start")
            if surgery.required_staff_role is not None:
                assigned_roles = set()
                for a in self.assignment_repo.get_active_for_surgery(surgery_id):
                    staff = self.staff_service.staff_repo.get_by_id(a.staff_id)
                    if staff:
                        assigned_roles.add(staff.role)
                if surgery.required_staff_role not in assigned_roles:
                    raise ConflictError(
                        f"Surgery {surgery_id} requires an assigned {surgery.required_staff_role.value} before it can start"
                    )
            now = utc_now()
            if not self.theatre_repo.set_status_if(theatre.id, TheatreStatus.AVAILABLE, TheatreStatus.IN_USE):
                raise ConflictError(f"Theatre {theatre.name} changed state; surgery cannot start")
            if not self.surgery_repo.set_status_if(surgery_id, SurgeryStatus.SCHEDULED, SurgeryStatus.IN_PROGRESS, started_at=now):
                raise ConflictError(f"Surgery {surgery_id} was modified by another operation")
            self.audit.record(
                FlowEventType.SURGERY_STARTED, actor=actor, patient_id=surgery.patient_id,
                resource_type=ResourceType.SURGERY, resource_id=surgery_id, department_id=surgery.department_id,
                previous_state=SurgeryStatus.SCHEDULED.value, new_state=SurgeryStatus.IN_PROGRESS.value,
                notes=notes or f"Surgery started in theatre {theatre.name}", metadata={"theatreId": theatre.id},
            )
            self.audit.record(
                FlowEventType.THEATRE_STATUS_CHANGE, actor=actor, patient_id=surgery.patient_id,
                resource_type=ResourceType.THEATRE, resource_id=theatre.id, department_id=theatre.department_id,
                previous_state=TheatreStatus.AVAILABLE.value, new_state=TheatreStatus.IN_USE.value,
                notes=f"Surgery {surgery_id} started", metadata={"surgeryId": surgery_id},
            )
            outbox.add("SURGERY_UPDATED", ResourceType.SURGERY, surgery_id, actor,
                       patient_id=surgery.patient_id, department_id=surgery.department_id,
                       previous_state=SurgeryStatus.SCHEDULED.value, new_state=SurgeryStatus.IN_PROGRESS.value)
            outbox.add("THEATRE_UPDATED", ResourceType.THEATRE, theatre.id, actor,
                       department_id=theatre.department_id,
                       previous_state=TheatreStatus.AVAILABLE.value, new_state=TheatreStatus.IN_USE.value)
            updated = self._require_surgery(surgery_id)
        return updated

    def complete_surgery(self, surgery_id: int, notes: str = "", actor: Actor = SYSTEM_ACTOR) -> Surgery:
        """IN_PROGRESS -> COMPLETED; slot COMPLETED; theatre IN_USE -> CLEANING;
        active staff assignments released (staff -> AVAILABLE)."""
        with self.transaction() as outbox:
            surgery = self._require_surgery(surgery_id)
            SurgeryPolicy.validate_transition(surgery.status, SurgeryStatus.COMPLETED)
            now = utc_now()
            theatre = self.theatre_repo.get_by_id(surgery.theatre_id) if surgery.theatre_id else None
            if surgery.slot_id is not None:
                if not self.slot_repo.complete_booking(surgery.slot_id, surgery_id):
                    raise ConflictError(f"Theatre slot {surgery.slot_id} is not booked by surgery {surgery_id}")
                self.audit.record(
                    FlowEventType.THEATRE_SLOT_COMPLETED, actor=actor, patient_id=surgery.patient_id,
                    resource_type=ResourceType.THEATRE_SLOT, resource_id=surgery.slot_id,
                    department_id=theatre.department_id if theatre else surgery.department_id,
                    previous_state=TheatreSlotStatus.BOOKED.value, new_state=TheatreSlotStatus.COMPLETED.value,
                    notes=f"Surgery {surgery_id} completed", metadata={"surgeryId": surgery_id},
                )
                outbox.add("THEATRE_SLOT_UPDATED", ResourceType.THEATRE_SLOT, surgery.slot_id, actor,
                           patient_id=surgery.patient_id,
                           department_id=theatre.department_id if theatre else surgery.department_id,
                           previous_state=TheatreSlotStatus.BOOKED.value, new_state=TheatreSlotStatus.COMPLETED.value)
            if theatre is not None:
                if not self.theatre_repo.set_status_if(theatre.id, TheatreStatus.IN_USE, TheatreStatus.CLEANING):
                    raise ConflictError(f"Theatre {theatre.name} is not IN_USE by surgery {surgery_id}")
                self.audit.record(
                    FlowEventType.THEATRE_STATUS_CHANGE, actor=actor, patient_id=surgery.patient_id,
                    resource_type=ResourceType.THEATRE, resource_id=theatre.id, department_id=theatre.department_id,
                    previous_state=TheatreStatus.IN_USE.value, new_state=TheatreStatus.CLEANING.value,
                    notes=f"Surgery {surgery_id} completed; theatre needs cleaning", metadata={"surgeryId": surgery_id},
                )
                outbox.add("THEATRE_UPDATED", ResourceType.THEATRE, theatre.id, actor,
                           department_id=theatre.department_id,
                           previous_state=TheatreStatus.IN_USE.value, new_state=TheatreStatus.CLEANING.value)
            for assignment in self.assignment_repo.get_active_for_surgery(surgery_id):
                self.staff_service.release_assignment_in_transaction(
                    assignment, f"Surgery {surgery_id} completed", actor, EventSource.SYSTEM, outbox
                )
            if not self.surgery_repo.set_status_if(surgery_id, SurgeryStatus.IN_PROGRESS, SurgeryStatus.COMPLETED, completed_at=now):
                raise ConflictError(f"Surgery {surgery_id} was modified by another operation")
            self.audit.record(
                FlowEventType.SURGERY_COMPLETED, actor=actor, patient_id=surgery.patient_id,
                resource_type=ResourceType.SURGERY, resource_id=surgery_id, department_id=surgery.department_id,
                previous_state=SurgeryStatus.IN_PROGRESS.value, new_state=SurgeryStatus.COMPLETED.value,
                notes=notes or "Surgery completed",
                metadata={"theatreId": surgery.theatre_id, "slotId": surgery.slot_id},
            )
            outbox.add("SURGERY_UPDATED", ResourceType.SURGERY, surgery_id, actor,
                       patient_id=surgery.patient_id, department_id=surgery.department_id,
                       previous_state=SurgeryStatus.IN_PROGRESS.value, new_state=SurgeryStatus.COMPLETED.value)
            updated = self._require_surgery(surgery_id)
        return updated

    def cancel_surgery(self, surgery_id: int, notes: str = "", actor: Actor = SYSTEM_ACTOR) -> Surgery:
        """WAITING/SCHEDULED -> CANCELLED; releases slot + staff; removes queue entry."""
        with self.transaction() as outbox:
            surgery = self._require_surgery(surgery_id)
            SurgeryPolicy.validate_transition(surgery.status, SurgeryStatus.CANCELLED)
            previous = surgery.status
            self._release_slot(surgery, FlowEventType.THEATRE_SLOT_RELEASED, actor, EventSource.MANUAL, outbox,
                               notes or "Surgery cancelled")
            for assignment in self.assignment_repo.get_active_for_surgery(surgery_id):
                self.staff_service.release_assignment_in_transaction(
                    assignment, f"Surgery {surgery_id} cancelled", actor, EventSource.SYSTEM, outbox
                )
            self._resolve_theatre_entry(surgery, WaitlistStatus.CANCELLED, None, actor, EventSource.MANUAL, outbox,
                                        notes or "Surgery cancelled")
            if not self.surgery_repo.set_status_if(surgery_id, previous, SurgeryStatus.CANCELLED, theatre_id=None, slot_id=None):
                raise ConflictError(f"Surgery {surgery_id} was modified by another operation")
            self.audit.record(
                FlowEventType.SURGERY_CANCELLED, actor=actor, patient_id=surgery.patient_id,
                resource_type=ResourceType.SURGERY, resource_id=surgery_id, department_id=surgery.department_id,
                previous_state=previous.value, new_state=SurgeryStatus.CANCELLED.value,
                notes=notes or "Surgery cancelled", metadata={"slotId": surgery.slot_id},
            )
            outbox.add("SURGERY_UPDATED", ResourceType.SURGERY, surgery_id, actor,
                       patient_id=surgery.patient_id, department_id=surgery.department_id,
                       previous_state=previous.value, new_state=SurgeryStatus.CANCELLED.value)
            updated = self._require_surgery(surgery_id)
        return updated
