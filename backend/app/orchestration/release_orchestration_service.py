"""Resource release + automatic matching.

The core operational chain:

    RESOURCE BECOMES AVAILABLE (release committed)
      -> waiting queue evaluated (MatchingService.find_candidates)
      -> deterministic match identified
      -> validated assignment performed via the standard workflow
      -> audit + realtime events (after commit)

The release and each auto-assignment attempt are separate transactions, so a
rejected assignment never undoes the release. Auto-assignment is enabled by
``settings.AUTO_ASSIGN_ON_RELEASE`` and can be overridden per request.
"""
from dataclasses import dataclass, field
from typing import List, Optional

from app.application.matching_service import AutoAssignmentResult, MatchingService
from app.application.bed_service import BedService
from app.application.staff_service import StaffService
from app.application.surgery_service import SurgeryService
from app.application.theatre_service import TheatreService
from app.core.config import settings
from app.domain.entities import Actor, SYSTEM_ACTOR
from app.domain.enums import BedStatus, ResourceType, StaffStatus, TheatreStatus
from app.domain.policies import NotFoundError
from app.orchestration.flow_orchestration_service import FlowOrchestrationService


@dataclass
class ReleaseOutcome:
    """Generic wrapper: the released/updated resource plus what auto-matching did."""

    resource: object
    auto_assignments: List[AutoAssignmentResult] = field(default_factory=list)

    @property
    def auto_assignment(self) -> Optional[AutoAssignmentResult]:
        return self.auto_assignments[0] if self.auto_assignments else None


class ReleaseOrchestrationService:
    def __init__(
        self,
        flow: FlowOrchestrationService,
        bed_service: BedService,
        theatre_service: TheatreService,
        surgery_service: SurgeryService,
        staff_service: StaffService,
        matching: MatchingService,
    ):
        self.flow = flow
        self.bed_service = bed_service
        self.theatre_service = theatre_service
        self.surgery_service = surgery_service
        self.staff_service = staff_service
        self.matching = matching

    @staticmethod
    def _should_auto_assign(override: Optional[bool]) -> bool:
        return settings.AUTO_ASSIGN_ON_RELEASE if override is None else override

    # ------------------------------------------------------------------
    # Beds
    # ------------------------------------------------------------------
    def release_bed(self, bed_id: int, notes: str, actor: Actor = SYSTEM_ACTOR, auto_assign: Optional[bool] = None) -> ReleaseOutcome:
        bed = self.flow.release_bed(bed_id, notes, actor)
        outcome = ReleaseOutcome(bed)
        if self._should_auto_assign(auto_assign):
            outcome.auto_assignments.append(self.matching.auto_assign(ResourceType.BED, bed_id, actor))
            outcome.resource = self.flow.bed_repo.get_by_id(bed_id)
        return outcome

    def update_bed_status(self, bed_id: int, new_status: BedStatus, notes: str, actor: Actor = SYSTEM_ACTOR,
                          auto_assign: Optional[bool] = None) -> ReleaseOutcome:
        bed = self.bed_service.update_bed_status(bed_id, new_status, notes, actor)
        outcome = ReleaseOutcome(bed)
        if new_status == BedStatus.AVAILABLE and self._should_auto_assign(auto_assign):
            outcome.auto_assignments.append(self.matching.auto_assign(ResourceType.BED, bed_id, actor))
            outcome.resource = self.flow.bed_repo.get_by_id(bed_id)
        return outcome

    # ------------------------------------------------------------------
    # Theatres / slots: only slots that are genuinely AVAILABLE are evaluated
    # ------------------------------------------------------------------
    def _match_available_slots(self, theatre_id: int, actor: Actor) -> List[AutoAssignmentResult]:
        results = []
        for slot in self.theatre_service.available_slots_for_theatre(theatre_id):
            results.append(self.matching.auto_assign(ResourceType.THEATRE_SLOT, slot.id, actor))
        return results

    def release_theatre(self, theatre_id: int, notes: str, actor: Actor = SYSTEM_ACTOR, auto_assign: Optional[bool] = None) -> ReleaseOutcome:
        theatre = self.theatre_service.release_theatre(theatre_id, notes, actor)
        outcome = ReleaseOutcome(theatre)
        if self._should_auto_assign(auto_assign):
            outcome.auto_assignments = self._match_available_slots(theatre_id, actor)
        return outcome

    def update_theatre_status(self, theatre_id: int, new_status: TheatreStatus, notes: str, actor: Actor = SYSTEM_ACTOR,
                              auto_assign: Optional[bool] = None) -> ReleaseOutcome:
        theatre = self.theatre_service.update_theatre_status(theatre_id, new_status, notes, actor)
        outcome = ReleaseOutcome(theatre)
        if new_status == TheatreStatus.AVAILABLE and self._should_auto_assign(auto_assign):
            outcome.auto_assignments = self._match_available_slots(theatre_id, actor)
        return outcome

    def create_slot(self, theatre_id: int, start_time, end_time, actor: Actor = SYSTEM_ACTOR,
                    auto_assign: Optional[bool] = None) -> ReleaseOutcome:
        slot = self.theatre_service.create_slot(theatre_id, start_time, end_time, actor)
        outcome = ReleaseOutcome(slot)
        if self._should_auto_assign(auto_assign):
            outcome.auto_assignments.append(self.matching.auto_assign(ResourceType.THEATRE_SLOT, slot.id, actor))
            outcome.resource = self.theatre_service.get_slot(slot.id)
        return outcome

    def unschedule_surgery(self, surgery_id: int, notes: str, actor: Actor = SYSTEM_ACTOR,
                           auto_assign: Optional[bool] = None) -> ReleaseOutcome:
        before = self.surgery_service.get_surgery(surgery_id)
        if not before:
            raise NotFoundError(f"Surgery with id {surgery_id} not found")
        surgery = self.surgery_service.unschedule_surgery(surgery_id, notes, actor)
        outcome = ReleaseOutcome(surgery)
        if before.slot_id is not None and self._should_auto_assign(auto_assign):
            outcome.auto_assignments.append(self.matching.auto_assign(ResourceType.THEATRE_SLOT, before.slot_id, actor))
            outcome.resource = self.surgery_service.get_surgery(surgery_id)
        return outcome

    def cancel_surgery(self, surgery_id: int, notes: str, actor: Actor = SYSTEM_ACTOR,
                       auto_assign: Optional[bool] = None) -> ReleaseOutcome:
        before = self.surgery_service.get_surgery(surgery_id)
        if not before:
            raise NotFoundError(f"Surgery with id {surgery_id} not found")
        released_staff = [a.staff_id for a in self.surgery_service.assignment_repo.get_active_for_surgery(surgery_id)]
        surgery = self.surgery_service.cancel_surgery(surgery_id, notes, actor)
        outcome = ReleaseOutcome(surgery)
        if self._should_auto_assign(auto_assign):
            if before.slot_id is not None:
                outcome.auto_assignments.append(self.matching.auto_assign(ResourceType.THEATRE_SLOT, before.slot_id, actor))
            for staff_id in released_staff:
                outcome.auto_assignments.append(self.matching.auto_assign(ResourceType.STAFF, staff_id, actor))
        return outcome

    def complete_surgery(self, surgery_id: int, notes: str, actor: Actor = SYSTEM_ACTOR,
                         auto_assign: Optional[bool] = None) -> ReleaseOutcome:
        released_staff = [a.staff_id for a in self.surgery_service.assignment_repo.get_active_for_surgery(surgery_id)]
        surgery = self.surgery_service.complete_surgery(surgery_id, notes, actor)
        outcome = ReleaseOutcome(surgery)
        if self._should_auto_assign(auto_assign):
            for staff_id in released_staff:
                outcome.auto_assignments.append(self.matching.auto_assign(ResourceType.STAFF, staff_id, actor))
        return outcome

    # ------------------------------------------------------------------
    # Staff
    # ------------------------------------------------------------------
    def release_assignment(self, assignment_id: int, notes: str, actor: Actor = SYSTEM_ACTOR,
                           auto_assign: Optional[bool] = None) -> ReleaseOutcome:
        assignment = self.staff_service.release_assignment(assignment_id, notes, actor)
        outcome = ReleaseOutcome(assignment)
        if self._should_auto_assign(auto_assign):
            outcome.auto_assignments.append(self.matching.auto_assign(ResourceType.STAFF, assignment.staff_id, actor))
        return outcome

    def update_staff_status(self, staff_id: int, new_status: StaffStatus, notes: str, actor: Actor = SYSTEM_ACTOR,
                            auto_assign: Optional[bool] = None) -> ReleaseOutcome:
        staff = self.staff_service.update_staff_status(staff_id, new_status, notes, actor)
        outcome = ReleaseOutcome(staff)
        if new_status == StaffStatus.AVAILABLE and self._should_auto_assign(auto_assign):
            outcome.auto_assignments.append(self.matching.auto_assign(ResourceType.STAFF, staff_id, actor))
            outcome.resource = self.staff_service.get_staff(staff_id)
        return outcome
