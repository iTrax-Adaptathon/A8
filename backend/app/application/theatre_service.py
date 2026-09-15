"""Theatres and theatre slots.

Theatre status and slot status are independent:
* a Theatre is AVAILABLE / IN_USE / CLEANING / UNAVAILABLE as a room;
* a TheatreSlot is a bookable time window (AVAILABLE / BOOKED / COMPLETED / CANCELLED).

Scheduling always targets a specific AVAILABLE slot whose parent theatre is
active and AVAILABLE. Overlapping live slots in one theatre are rejected.
"""
from datetime import datetime
from typing import List, Optional

from app.application.audit_service import AuditService, TransactionalService
from app.domain.entities import Actor, SYSTEM_ACTOR, Theatre, TheatreSlot
from app.domain.enums import FlowEventType, ResourceType, TheatreSlotStatus, TheatreStatus
from app.domain.policies import (
    ConflictError,
    NotFoundError,
    TheatrePolicy,
    TheatreSlotPolicy,
)
from app.infrastructure.repositories import (
    DepartmentRepository,
    FlowEventRepository,
    TheatreRepository,
    TheatreSlotRepository,
)
from app.realtime.event_bus import EventBus


class TheatreService(TransactionalService):
    def __init__(
        self,
        theatre_repo: TheatreRepository,
        slot_repo: Optional[TheatreSlotRepository] = None,
        department_repo: Optional[DepartmentRepository] = None,
        flow_event_repo: Optional[FlowEventRepository] = None,
        event_bus: Optional[EventBus] = None,
    ):
        db = theatre_repo.db
        super().__init__(db, AuditService(flow_event_repo or FlowEventRepository(db)), event_bus)
        self.theatre_repo = theatre_repo
        self.slot_repo = slot_repo or TheatreSlotRepository(db)
        self.department_repo = department_repo or DepartmentRepository(db)

    # ------------------------------------------------------------------
    # Theatres
    # ------------------------------------------------------------------
    def get_theatre(self, theatre_id: int) -> Optional[Theatre]:
        return self.theatre_repo.get_by_id(theatre_id)

    def _require_theatre(self, theatre_id: int) -> Theatre:
        theatre = self.theatre_repo.get_by_id(theatre_id)
        if not theatre:
            raise NotFoundError(f"Theatre with id {theatre_id} not found")
        return theatre

    def list_theatres(
        self,
        department_id: Optional[int] = None,
        status: Optional[TheatreStatus] = None,
        include_inactive: bool = False,
        limit: Optional[int] = None,
        offset: int = 0,
    ) -> List[Theatre]:
        return self.theatre_repo.get_all(department_id, status, include_inactive, limit, offset)

    def count_theatres(
        self,
        department_id: Optional[int] = None,
        status: Optional[TheatreStatus] = None,
        include_inactive: bool = False,
    ) -> int:
        return self.theatre_repo.count(department_id, status, include_inactive)

    def create_theatre(self, theatre: Theatre, actor: Actor = SYSTEM_ACTOR) -> Theatre:
        if theatre.status == TheatreStatus.IN_USE:
            raise ConflictError("A theatre cannot be created IN_USE; start a surgery instead.")
        department = self.department_repo.get_by_id(theatre.department_id)
        if not department:
            raise NotFoundError(f"Department with id {theatre.department_id} not found")
        if not department.is_active:
            raise ConflictError(f"Department {department.name} is inactive")
        with self.transaction() as outbox:
            created = self.theatre_repo.create(theatre)
            self.audit.record(
                FlowEventType.RESOURCE_CREATED,
                actor=actor,
                resource_type=ResourceType.THEATRE,
                resource_id=created.id,
                department_id=created.department_id,
                new_state=created.status.value,
                notes=f"Theatre {created.name} created",
            )
            outbox.add("THEATRE_UPDATED", ResourceType.THEATRE, created.id, actor,
                       department_id=created.department_id, new_state=created.status.value)
        return created

    def update_theatre_status(
        self, theatre_id: int, new_status: TheatreStatus, notes: str = "", actor: Actor = SYSTEM_ACTOR
    ) -> Theatre:
        with self.transaction() as outbox:
            theatre = self._require_theatre(theatre_id)
            if not theatre.is_active:
                raise ConflictError(f"Theatre {theatre.name} is inactive")
            TheatrePolicy.validate_status_transition(theatre.status, new_status)
            if not self.theatre_repo.set_status_if(theatre_id, theatre.status, new_status):
                raise ConflictError(f"Theatre {theatre.name} changed state during the update")
            self.audit.record(
                FlowEventType.THEATRE_STATUS_CHANGE,
                actor=actor,
                resource_type=ResourceType.THEATRE,
                resource_id=theatre_id,
                department_id=theatre.department_id,
                previous_state=theatre.status.value,
                new_state=new_status.value,
                notes=notes or f"Theatre {theatre.name} status changed",
            )
            outbox.add("THEATRE_UPDATED", ResourceType.THEATRE, theatre_id, actor,
                       department_id=theatre.department_id,
                       previous_state=theatre.status.value, new_state=new_status.value)
            updated = self._require_theatre(theatre_id)
        return updated

    def release_theatre(self, theatre_id: int, notes: str = "Theatre cleaned", actor: Actor = SYSTEM_ACTOR) -> Theatre:
        """CLEANING -> AVAILABLE. Slots are NOT touched; only slots that are
        already AVAILABLE become matchable again (see ReleaseOrchestrationService)."""
        with self.transaction() as outbox:
            theatre = self._require_theatre(theatre_id)
            if not theatre.is_active:
                raise ConflictError(f"Theatre {theatre.name} is inactive")
            TheatrePolicy.validate_release(theatre.status)
            if not self.theatre_repo.set_status_if(theatre_id, TheatreStatus.CLEANING, TheatreStatus.AVAILABLE):
                raise ConflictError(f"Theatre {theatre.name} changed state during release")
            self.audit.record(
                FlowEventType.THEATRE_STATUS_CHANGE,
                actor=actor,
                resource_type=ResourceType.THEATRE,
                resource_id=theatre_id,
                department_id=theatre.department_id,
                previous_state=TheatreStatus.CLEANING.value,
                new_state=TheatreStatus.AVAILABLE.value,
                notes=notes,
            )
            outbox.add("THEATRE_UPDATED", ResourceType.THEATRE, theatre_id, actor,
                       department_id=theatre.department_id,
                       previous_state=TheatreStatus.CLEANING.value, new_state=TheatreStatus.AVAILABLE.value)
            updated = self._require_theatre(theatre_id)
        return updated

    def deactivate_theatre(self, theatre_id: int, notes: str = "", actor: Actor = SYSTEM_ACTOR) -> Theatre:
        with self.transaction() as outbox:
            theatre = self._require_theatre(theatre_id)
            if not theatre.is_active:
                raise ConflictError(f"Theatre {theatre.name} is already inactive")
            TheatrePolicy.validate_deactivation(theatre, self.slot_repo.count_booked_for_theatre(theatre_id))
            self.theatre_repo.set_active(theatre_id, False)
            self.audit.record(
                FlowEventType.RESOURCE_DEACTIVATED,
                actor=actor,
                resource_type=ResourceType.THEATRE,
                resource_id=theatre_id,
                department_id=theatre.department_id,
                previous_state=theatre.status.value,
                new_state="INACTIVE",
                notes=notes or f"Theatre {theatre.name} deactivated",
            )
            outbox.add("THEATRE_UPDATED", ResourceType.THEATRE, theatre_id, actor,
                       department_id=theatre.department_id,
                       previous_state=theatre.status.value, new_state="INACTIVE")
            updated = self._require_theatre(theatre_id)
        return updated

    # ------------------------------------------------------------------
    # Slots
    # ------------------------------------------------------------------
    def get_slot(self, slot_id: int) -> Optional[TheatreSlot]:
        return self.slot_repo.get_by_id(slot_id)

    def _require_slot(self, slot_id: int) -> TheatreSlot:
        slot = self.slot_repo.get_by_id(slot_id)
        if not slot:
            raise NotFoundError(f"Theatre slot with id {slot_id} not found")
        return slot

    def list_slots(
        self,
        theatre_id: Optional[int] = None,
        status: Optional[TheatreSlotStatus] = None,
        surgery_id: Optional[int] = None,
        start_from: Optional[datetime] = None,
        start_to: Optional[datetime] = None,
        limit: Optional[int] = None,
        offset: int = 0,
    ) -> List[TheatreSlot]:
        return self.slot_repo.get_all(theatre_id, status, surgery_id, start_from, start_to, limit, offset)

    def count_slots(
        self,
        theatre_id: Optional[int] = None,
        status: Optional[TheatreSlotStatus] = None,
        surgery_id: Optional[int] = None,
        start_from: Optional[datetime] = None,
        start_to: Optional[datetime] = None,
    ) -> int:
        return self.slot_repo.count(theatre_id, status, surgery_id, start_from, start_to)

    def available_slots_for_theatre(self, theatre_id: int) -> List[TheatreSlot]:
        return self.slot_repo.get_all(theatre_id=theatre_id, status=TheatreSlotStatus.AVAILABLE)

    def create_slot(self, theatre_id: int, start_time: datetime, end_time: datetime, actor: Actor = SYSTEM_ACTOR) -> TheatreSlot:
        with self.transaction() as outbox:
            theatre = self._require_theatre(theatre_id)
            if not theatre.is_active:
                raise ConflictError(f"Theatre {theatre.name} is inactive")
            TheatreSlotPolicy.validate_window(start_time, end_time)
            TheatreSlotPolicy.validate_no_overlap(start_time, end_time, self.slot_repo.get_live_slots_for_theatre(theatre_id))
            created = self.slot_repo.create(
                TheatreSlot(id=None, theatre_id=theatre_id, start_time=start_time, end_time=end_time)
            )
            self.audit.record(
                FlowEventType.THEATRE_SLOT_CREATED,
                actor=actor,
                resource_type=ResourceType.THEATRE_SLOT,
                resource_id=created.id,
                department_id=theatre.department_id,
                new_state=created.status.value,
                notes=f"Slot {created.start_time.isoformat()} - {created.end_time.isoformat()} in theatre {theatre.name}",
                metadata={"theatreId": theatre_id},
            )
            outbox.add("THEATRE_SLOT_UPDATED", ResourceType.THEATRE_SLOT, created.id, actor,
                       department_id=theatre.department_id, new_state=created.status.value)
        return created

    def cancel_slot(self, slot_id: int, notes: str = "", actor: Actor = SYSTEM_ACTOR) -> TheatreSlot:
        with self.transaction() as outbox:
            slot = self._require_slot(slot_id)
            TheatreSlotPolicy.validate_cancellable(slot)
            theatre = self._require_theatre(slot.theatre_id)
            if not self.slot_repo.cancel_if_available(slot_id):
                raise ConflictError(f"Theatre slot {slot_id} changed state during cancellation")
            self.audit.record(
                FlowEventType.THEATRE_SLOT_CANCELLED,
                actor=actor,
                resource_type=ResourceType.THEATRE_SLOT,
                resource_id=slot_id,
                department_id=theatre.department_id,
                previous_state=TheatreSlotStatus.AVAILABLE.value,
                new_state=TheatreSlotStatus.CANCELLED.value,
                notes=notes or "Slot cancelled",
                metadata={"theatreId": slot.theatre_id},
            )
            outbox.add("THEATRE_SLOT_UPDATED", ResourceType.THEATRE_SLOT, slot_id, actor,
                       department_id=theatre.department_id,
                       previous_state=TheatreSlotStatus.AVAILABLE.value, new_state=TheatreSlotStatus.CANCELLED.value)
            updated = self._require_slot(slot_id)
        return updated
