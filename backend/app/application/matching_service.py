"""Deterministic matching of waiting patients/surgeries to a concrete resource.

MATCH IDENTIFIED (pure computation, `find_candidates`) is kept separate from
ASSIGNMENT CONFIRMED (`confirm`). Confirmation always goes through the very
same validated workflow a manual assignment uses:

* BED          -> FlowOrchestrationService.admit_patient / transfer_patient
* THEATRE_SLOT -> SurgeryService.schedule_surgery
* STAFF        -> StaffService.assign_staff

Given the same database state the candidate list is always identical: the
queue is read in WaitlistPolicy order (priority, requested_at, id) and every
eligibility rule is an explicit predicate in MatchingPolicy. Nothing here is
statistical or learned.
"""
from dataclasses import dataclass, field
from typing import Dict, List, Optional

from app.application.audit_service import AuditService, TransactionalService
from app.application.staff_service import StaffService
from app.application.surgery_service import SurgeryService
from app.domain.entities import Actor, SYSTEM_ACTOR, WaitlistEntry
from app.domain.enums import (
    BedStatus,
    EventSource,
    FlowEventType,
    PatientStatus,
    ResourceType,
    StaffAssignmentType,
    StaffStatus,
    TheatreSlotStatus,
    TheatreStatus,
    WaitlistResourceType,
    WaitlistStatus,
)
from app.domain.policies import (
    ConflictError,
    DomainValidationError,
    MatchingPolicy,
    NotFoundError,
    PatientPolicy,
    utc_now,
)
from app.infrastructure.repositories import (
    BedRepository,
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
from app.orchestration.flow_orchestration_service import FlowOrchestrationService
from app.realtime.event_bus import EventBus

MATCHABLE_RESOURCE_TYPES = (ResourceType.BED, ResourceType.THEATRE_SLOT, ResourceType.STAFF)


@dataclass
class MatchCandidate:
    rank: int
    waitlist_entry: WaitlistEntry
    patient_id: int
    surgery_id: Optional[int]
    reason: str


@dataclass
class MatchResult:
    resource_type: ResourceType
    resource_id: int
    resource_available: bool
    department_id: Optional[int]
    candidates: List[MatchCandidate] = field(default_factory=list)


@dataclass
class AutoAssignmentResult:
    resource_type: ResourceType
    resource_id: int
    matched: bool
    waitlist_entry_id: Optional[int] = None
    patient_id: Optional[int] = None
    surgery_id: Optional[int] = None
    reason: Optional[str] = None
    candidates_evaluated: int = 0
    rejections: List[Dict[str, object]] = field(default_factory=list)


class MatchingService(TransactionalService):
    def __init__(
        self,
        flow_orchestrator: FlowOrchestrationService,
        surgery_service: SurgeryService,
        staff_service: StaffService,
        waitlist_repo: Optional[WaitlistRepository] = None,
        flow_event_repo: Optional[FlowEventRepository] = None,
        event_bus: Optional[EventBus] = None,
    ):
        db = flow_orchestrator.db
        super().__init__(db, AuditService(flow_event_repo or FlowEventRepository(db)), event_bus)
        self.flow = flow_orchestrator
        self.surgery_service = surgery_service
        self.staff_service = staff_service
        self.waitlist_repo = waitlist_repo or WaitlistRepository(db)
        self.bed_repo: BedRepository = flow_orchestrator.bed_repo
        self.patient_repo: PatientRepository = flow_orchestrator.patient_repo
        self.department_repo: DepartmentRepository = flow_orchestrator.department_repo
        self.surgery_repo: SurgeryRepository = surgery_service.surgery_repo
        self.theatre_repo: TheatreRepository = surgery_service.theatre_repo
        self.slot_repo: TheatreSlotRepository = surgery_service.slot_repo
        self.staff_repo: StaffRepository = staff_service.staff_repo
        self.assignment_repo: StaffAssignmentRepository = staff_service.assignment_repo

    # ------------------------------------------------------------------
    # MATCH IDENTIFIED (read-only)
    # ------------------------------------------------------------------
    def find_candidates(self, resource_type: ResourceType, resource_id: int) -> MatchResult:
        """Pure computation. Never writes to the database."""
        if resource_type == ResourceType.BED:
            return self._bed_candidates(resource_id)
        if resource_type == ResourceType.THEATRE_SLOT:
            return self._slot_candidates(resource_id)
        if resource_type == ResourceType.STAFF:
            return self._staff_candidates(resource_id)
        raise DomainValidationError(
            f"resourceType must be one of {', '.join(t.value for t in MATCHABLE_RESOURCE_TYPES)}"
        )

    @staticmethod
    def _rank_text(rank: int) -> str:
        return "longest waiting eligible patient" if rank == 1 else f"rank {rank} in queue"

    def _department_name(self, department_id: int) -> str:
        department = self.department_repo.get_by_id(department_id)
        return department.name if department else f"department {department_id}"

    def _bed_candidates(self, bed_id: int) -> MatchResult:
        bed = self.bed_repo.get_by_id(bed_id)
        if not bed:
            raise NotFoundError(f"Bed with id {bed_id} not found")
        result = MatchResult(ResourceType.BED, bed_id, False, bed.department_id)
        # The bed itself must be genuinely assignable (active, AVAILABLE, empty).
        if not bed.is_active or bed.status != BedStatus.AVAILABLE or bed.current_patient_id is not None:
            return result
        result.resource_available = True
        dept_name = self._department_name(bed.department_id)
        rank = 0
        for entry in self.waitlist_repo.get_waiting_queue(WaitlistResourceType.BED, bed.department_id):
            patient = self.patient_repo.get_by_id(entry.patient_id)
            if not patient or MatchingPolicy.bed_ineligibility(bed, entry, patient) is not None:
                continue
            rank += 1
            reason = (
                f"Compatible {dept_name} {bed.bed_type.value} bed; priority {entry.priority}; "
                f"{self._rank_text(rank)}."
            )
            result.candidates.append(MatchCandidate(rank, entry, entry.patient_id, None, reason))
        return result

    def _slot_candidates(self, slot_id: int) -> MatchResult:
        slot = self.slot_repo.get_by_id(slot_id)
        if not slot:
            raise NotFoundError(f"Theatre slot with id {slot_id} not found")
        theatre = self.theatre_repo.get_by_id(slot.theatre_id)
        if not theatre:
            raise NotFoundError(f"Theatre with id {slot.theatre_id} not found")
        result = MatchResult(ResourceType.THEATRE_SLOT, slot_id, False, theatre.department_id)
        now = utc_now()
        # The slot must be genuinely AVAILABLE and its parent theatre active + AVAILABLE.
        if slot.status != TheatreSlotStatus.AVAILABLE or slot.surgery_id is not None or not theatre.is_active \
                or theatre.status != TheatreStatus.AVAILABLE or slot.start_time < now:
            return result
        result.resource_available = True
        dept_name = self._department_name(theatre.department_id)
        rank = 0
        for entry in self.waitlist_repo.get_waiting_queue(WaitlistResourceType.THEATRE, theatre.department_id):
            if entry.surgery_id is None:
                continue
            surgery = self.surgery_repo.get_by_id(entry.surgery_id)
            patient = self.patient_repo.get_by_id(entry.patient_id)
            if not surgery or not patient:
                continue
            if MatchingPolicy.slot_ineligibility(slot, theatre, surgery, patient, now) is not None:
                continue
            rank += 1
            reason = (
                f"Compatible {dept_name} theatre slot ({slot.duration_minutes} min >= {surgery.duration_minutes} min); "
                f"priority {entry.priority}; {self._rank_text(rank)}."
            )
            result.candidates.append(MatchCandidate(rank, entry, entry.patient_id, surgery.id, reason))
        return result

    def _staff_window(self, entry: WaitlistEntry):
        now = utc_now()
        if entry.surgery_id is not None:
            surgery = self.surgery_repo.get_by_id(entry.surgery_id)
            if surgery and surgery.slot_id is not None:
                slot = self.slot_repo.get_by_id(surgery.slot_id)
                if slot:
                    return slot.start_time, slot.end_time
        return now, None

    def _staff_candidates(self, staff_id: int) -> MatchResult:
        staff = self.staff_repo.get_by_id(staff_id)
        if not staff:
            raise NotFoundError(f"Staff with id {staff_id} not found")
        result = MatchResult(ResourceType.STAFF, staff_id, False, staff.department_id)
        has_active = self.assignment_repo.get_active_for_staff(staff_id) is not None
        if not staff.is_active or staff.status != StaffStatus.AVAILABLE or has_active:
            return result
        result.resource_available = True
        dept_name = self._department_name(staff.department_id)
        rank = 0
        for entry in self.waitlist_repo.get_waiting_queue(WaitlistResourceType.STAFF, staff.department_id):
            patient = self.patient_repo.get_by_id(entry.patient_id)
            if not patient or patient.current_status == PatientStatus.DISCHARGED:
                continue
            start, end = self._staff_window(entry)
            if MatchingPolicy.staff_ineligibility(staff, entry, has_active, start, end) is not None:
                continue
            rank += 1
            reason = (
                f"Compatible {dept_name} {staff.role.value} on shift; priority {entry.priority}; "
                f"{self._rank_text(rank)}."
            )
            result.candidates.append(MatchCandidate(rank, entry, entry.patient_id, entry.surgery_id, reason))
        return result

    # ------------------------------------------------------------------
    # ASSIGNMENT CONFIRMED
    # ------------------------------------------------------------------
    def confirm(
        self,
        resource_type: ResourceType,
        resource_id: int,
        waitlist_entry_id: int,
        actor: Actor = SYSTEM_ACTOR,
        source: EventSource = EventSource.MANUAL,
        notes: str = "",
    ) -> AutoAssignmentResult:
        """Record MATCH_IDENTIFIED and perform the assignment through the
        standard validated workflow. On failure the whole attempt is rolled
        back and an ASSIGNMENT_REJECTED event is stored instead."""
        entry = self.waitlist_repo.get_by_id(waitlist_entry_id)
        if not entry:
            raise NotFoundError(f"Waitlist entry with id {waitlist_entry_id} not found")
        if entry.status != WaitlistStatus.WAITING:
            raise ConflictError(f"Waitlist entry {waitlist_entry_id} is {entry.status.value}")

        match = self.find_candidates(resource_type, resource_id)
        candidate = next((c for c in match.candidates if c.waitlist_entry.id == waitlist_entry_id), None)
        if candidate is None:
            reason = self._ineligibility_reason(resource_type, resource_id, entry, match)
            self._record_rejection(resource_type, resource_id, entry, reason, actor, source)
            raise ConflictError(f"Waitlist entry {waitlist_entry_id} is not eligible for {resource_type.value} {resource_id}: {reason}")

        # MATCH_IDENTIFIED is flushed inside the same transaction as the assignment,
        # so it only persists if the assignment commits.
        self.audit.record(
            FlowEventType.MATCH_IDENTIFIED,
            actor=actor,
            source=source,
            patient_id=entry.patient_id,
            resource_type=resource_type,
            resource_id=resource_id,
            department_id=match.department_id,
            notes=candidate.reason,
            metadata={"waitlistEntryId": entry.id, "rank": candidate.rank, "surgeryId": candidate.surgery_id},
        )
        try:
            self._perform_assignment(resource_type, resource_id, entry, actor, source, notes or candidate.reason)
        except DomainValidationError as exc:
            # The workflow rolled everything back (including MATCH_IDENTIFIED).
            self._record_rejection(resource_type, resource_id, entry, str(exc), actor, source)
            raise
        # Realtime: the assignment workflow already emitted its own events; add the match event.
        self.event_bus.publish([
            _match_event(resource_type, resource_id, entry, actor, source)
        ])
        return AutoAssignmentResult(
            resource_type=resource_type,
            resource_id=resource_id,
            matched=True,
            waitlist_entry_id=entry.id,
            patient_id=entry.patient_id,
            surgery_id=candidate.surgery_id,
            reason=candidate.reason,
            candidates_evaluated=candidate.rank,
        )

    def _perform_assignment(self, resource_type, resource_id, entry: WaitlistEntry, actor, source, notes):
        if resource_type == ResourceType.BED:
            bed = self.bed_repo.get_by_id(resource_id)
            patient = self.patient_repo.get_by_id(entry.patient_id)
            if patient.current_status == PatientStatus.REGISTERED:
                self.flow.admit_patient(entry.patient_id, bed.department_id, resource_id, notes, actor, source)
            else:
                self.flow.transfer_patient(entry.patient_id, bed.department_id, resource_id, notes, actor, source)
        elif resource_type == ResourceType.THEATRE_SLOT:
            self.surgery_service.schedule_surgery(entry.surgery_id, resource_id, notes, actor, source)
        elif resource_type == ResourceType.STAFF:
            assignment_type = StaffAssignmentType.SURGERY if entry.surgery_id else StaffAssignmentType.PATIENT
            self.staff_service.assign_staff(
                resource_id, assignment_type, entry.surgery_id, entry.patient_id,
                required_role=entry.required_staff_role, notes=notes, actor=actor, source=source,
            )

    def _ineligibility_reason(self, resource_type, resource_id, entry: WaitlistEntry, match: MatchResult) -> str:
        if not match.resource_available:
            return f"{resource_type.value} {resource_id} is not available"
        patient = self.patient_repo.get_by_id(entry.patient_id)
        if resource_type == ResourceType.BED:
            if entry.resource_type != WaitlistResourceType.BED:
                return "entry is not a BED request"
            return MatchingPolicy.bed_ineligibility(self.bed_repo.get_by_id(resource_id), entry, patient) or "not eligible"
        if resource_type == ResourceType.THEATRE_SLOT:
            if entry.resource_type != WaitlistResourceType.THEATRE or entry.surgery_id is None:
                return "entry is not a THEATRE request"
            slot = self.slot_repo.get_by_id(resource_id)
            theatre = self.theatre_repo.get_by_id(slot.theatre_id)
            surgery = self.surgery_repo.get_by_id(entry.surgery_id)
            return MatchingPolicy.slot_ineligibility(slot, theatre, surgery, patient, utc_now()) or "not eligible"
        if entry.resource_type != WaitlistResourceType.STAFF:
            return "entry is not a STAFF request"
        staff = self.staff_repo.get_by_id(resource_id)
        start, end = self._staff_window(entry)
        return MatchingPolicy.staff_ineligibility(staff, entry, False, start, end) or "not eligible"

    def _record_rejection(self, resource_type, resource_id, entry: WaitlistEntry, reason: str, actor, source):
        with self.transaction():
            self.audit.record(
                FlowEventType.ASSIGNMENT_REJECTED,
                actor=actor,
                source=source,
                patient_id=entry.patient_id,
                resource_type=resource_type,
                resource_id=resource_id,
                department_id=entry.department_id,
                notes=reason,
                metadata={"waitlistEntryId": entry.id, "surgeryId": entry.surgery_id},
            )

    # ------------------------------------------------------------------
    # Automatic assignment after a resource became AVAILABLE
    # ------------------------------------------------------------------
    def auto_assign(self, resource_type: ResourceType, resource_id: int, actor: Actor = SYSTEM_ACTOR) -> AutoAssignmentResult:
        """Walk the deterministic candidate list and confirm the first one that
        the validated workflow accepts. Each attempt is its own transaction, so
        a rejected attempt can never undo the release that preceded it."""
        match = self.find_candidates(resource_type, resource_id)
        result = AutoAssignmentResult(resource_type=resource_type, resource_id=resource_id, matched=False)
        for candidate in match.candidates:
            result.candidates_evaluated += 1
            try:
                confirmed = self.confirm(
                    resource_type, resource_id, candidate.waitlist_entry.id, actor, EventSource.AUTO_MATCH,
                    notes=f"Auto-assigned: {candidate.reason}",
                )
            except DomainValidationError as exc:
                result.rejections.append({"waitlistEntryId": candidate.waitlist_entry.id, "reason": str(exc)})
                continue
            confirmed.candidates_evaluated = result.candidates_evaluated
            confirmed.rejections = result.rejections
            return confirmed
        return result


def _match_event(resource_type, resource_id, entry: WaitlistEntry, actor, source):
    from app.realtime.event_bus import RealtimeEvent

    return RealtimeEvent(
        type="MATCH_ASSIGNED",
        resource_type=resource_type.value,
        resource_id=resource_id,
        patient_id=entry.patient_id,
        department_id=entry.department_id,
        previous_state=WaitlistStatus.WAITING.value,
        new_state=WaitlistStatus.FULFILLED.value,
        actor_id=actor.id,
        source=source.value,
    )

