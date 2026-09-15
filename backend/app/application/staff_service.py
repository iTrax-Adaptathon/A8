"""Staff and staff assignments.

Rules (StaffPolicy):
* Statuses: AVAILABLE (on shift, free), ASSIGNED (one ACTIVE assignment), OFF_DUTY.
* shift_start / shift_end are the working hours; an assignment window must
  fall inside them.
* A staff member holds at most ONE active assignment at a time (enforced by a
  unique partial index and an atomic status claim).
* Role and department must match the assignment target.
"""
from datetime import datetime
from typing import List, Optional, Tuple

from app.application.audit_service import AuditService, Outbox, TransactionalService
from app.domain.entities import Actor, SYSTEM_ACTOR, Staff, StaffAssignment
from app.domain.enums import (
    EventSource,
    FlowEventType,
    ResourceType,
    StaffAssignmentStatus,
    StaffAssignmentType,
    StaffRole,
    StaffStatus,
    SurgeryStatus,
    WaitlistResourceType,
    WaitlistStatus,
)
from app.domain.policies import (
    ConflictError,
    DomainValidationError,
    NotFoundError,
    PatientPolicy,
    StaffPolicy,
    utc_now,
)
from app.infrastructure.repositories import (
    DepartmentRepository,
    FlowEventRepository,
    PatientRepository,
    StaffAssignmentRepository,
    StaffRepository,
    SurgeryRepository,
    TheatreSlotRepository,
    WaitlistRepository,
)
from app.realtime.event_bus import EventBus


class StaffService(TransactionalService):
    def __init__(
        self,
        staff_repo: StaffRepository,
        assignment_repo: Optional[StaffAssignmentRepository] = None,
        department_repo: Optional[DepartmentRepository] = None,
        patient_repo: Optional[PatientRepository] = None,
        surgery_repo: Optional[SurgeryRepository] = None,
        slot_repo: Optional[TheatreSlotRepository] = None,
        waitlist_repo: Optional[WaitlistRepository] = None,
        flow_event_repo: Optional[FlowEventRepository] = None,
        event_bus: Optional[EventBus] = None,
    ):
        db = staff_repo.db
        super().__init__(db, AuditService(flow_event_repo or FlowEventRepository(db)), event_bus)
        self.staff_repo = staff_repo
        self.assignment_repo = assignment_repo or StaffAssignmentRepository(db)
        self.department_repo = department_repo or DepartmentRepository(db)
        self.patient_repo = patient_repo or PatientRepository(db)
        self.surgery_repo = surgery_repo or SurgeryRepository(db)
        self.slot_repo = slot_repo or TheatreSlotRepository(db)
        self.waitlist_repo = waitlist_repo or WaitlistRepository(db)

    # ------------------------------------------------------------------
    # Staff
    # ------------------------------------------------------------------
    def get_staff(self, staff_id: int) -> Optional[Staff]:
        return self.staff_repo.get_by_id(staff_id)

    def _require_staff(self, staff_id: int) -> Staff:
        staff = self.staff_repo.get_by_id(staff_id)
        if not staff:
            raise NotFoundError(f"Staff with id {staff_id} not found")
        return staff

    def list_staff(
        self,
        department_id: Optional[int] = None,
        role: Optional[StaffRole] = None,
        status: Optional[StaffStatus] = None,
        include_inactive: bool = False,
        limit: Optional[int] = None,
        offset: int = 0,
    ) -> List[Staff]:
        return self.staff_repo.get_all(department_id, role, status, include_inactive, limit, offset)

    def count_staff(
        self,
        department_id: Optional[int] = None,
        role: Optional[StaffRole] = None,
        status: Optional[StaffStatus] = None,
        include_inactive: bool = False,
    ) -> int:
        return self.staff_repo.count(department_id, role, status, include_inactive)

    def create_staff(self, staff: Staff, actor: Actor = SYSTEM_ACTOR) -> Staff:
        if staff.status == StaffStatus.ASSIGNED:
            raise ConflictError("Staff cannot be created as ASSIGNED; create an assignment instead.")
        if staff.shift_end <= staff.shift_start:
            raise DomainValidationError("shiftEnd must be after shiftStart")
        department = self.department_repo.get_by_id(staff.department_id)
        if not department:
            raise NotFoundError(f"Department with id {staff.department_id} not found")
        if not department.is_active:
            raise ConflictError(f"Department {department.name} is inactive")
        with self.transaction() as outbox:
            created = self.staff_repo.create(staff)
            self.audit.record(
                FlowEventType.RESOURCE_CREATED,
                actor=actor,
                resource_type=ResourceType.STAFF,
                resource_id=created.id,
                department_id=created.department_id,
                new_state=created.status.value,
                notes=f"Staff {created.name} ({created.role.value}) created",
            )
            outbox.add("STAFF_UPDATED", ResourceType.STAFF, created.id, actor,
                       department_id=created.department_id, new_state=created.status.value)
        return created

    def update_staff_status(self, staff_id: int, new_status: StaffStatus, notes: str = "", actor: Actor = SYSTEM_ACTOR) -> Staff:
        with self.transaction() as outbox:
            staff = self._require_staff(staff_id)
            if not staff.is_active:
                raise ConflictError(f"Staff {staff.name} is inactive")
            StaffPolicy.validate_status_transition(staff.status, new_status)
            if not self.staff_repo.set_status_if(staff_id, staff.status, new_status):
                raise ConflictError(f"Staff {staff.name} changed state during the update")
            self.audit.record(
                FlowEventType.STAFF_STATUS_CHANGE,
                actor=actor,
                resource_type=ResourceType.STAFF,
                resource_id=staff_id,
                department_id=staff.department_id,
                previous_state=staff.status.value,
                new_state=new_status.value,
                notes=notes or f"Staff {staff.name} status changed",
            )
            outbox.add("STAFF_UPDATED", ResourceType.STAFF, staff_id, actor, department_id=staff.department_id,
                       previous_state=staff.status.value, new_state=new_status.value)
            updated = self._require_staff(staff_id)
        return updated

    def deactivate_staff(self, staff_id: int, notes: str = "", actor: Actor = SYSTEM_ACTOR) -> Staff:
        with self.transaction() as outbox:
            staff = self._require_staff(staff_id)
            if not staff.is_active:
                raise ConflictError(f"Staff {staff.name} is already inactive")
            StaffPolicy.validate_deactivation(staff)
            self.staff_repo.set_active(staff_id, False)
            self.audit.record(
                FlowEventType.RESOURCE_DEACTIVATED,
                actor=actor,
                resource_type=ResourceType.STAFF,
                resource_id=staff_id,
                department_id=staff.department_id,
                previous_state=staff.status.value,
                new_state="INACTIVE",
                notes=notes or f"Staff {staff.name} deactivated",
            )
            outbox.add("STAFF_UPDATED", ResourceType.STAFF, staff_id, actor, department_id=staff.department_id,
                       previous_state=staff.status.value, new_state="INACTIVE")
            updated = self._require_staff(staff_id)
        return updated

    # ------------------------------------------------------------------
    # Assignments
    # ------------------------------------------------------------------
    def get_assignment(self, assignment_id: int) -> Optional[StaffAssignment]:
        return self.assignment_repo.get_by_id(assignment_id)

    def list_assignments(
        self,
        staff_id: Optional[int] = None,
        status: Optional[StaffAssignmentStatus] = None,
        surgery_id: Optional[int] = None,
        patient_id: Optional[int] = None,
        limit: Optional[int] = None,
        offset: int = 0,
    ) -> List[StaffAssignment]:
        return self.assignment_repo.get_all(staff_id, status, surgery_id, patient_id, limit, offset)

    def count_assignments(
        self,
        staff_id: Optional[int] = None,
        status: Optional[StaffAssignmentStatus] = None,
        surgery_id: Optional[int] = None,
        patient_id: Optional[int] = None,
    ) -> int:
        return self.assignment_repo.count(staff_id, status, surgery_id, patient_id)

    def assignment_window(
        self, assignment_type: StaffAssignmentType, surgery_id: Optional[int], patient_id: Optional[int]
    ) -> Tuple[int, Optional[int], datetime, Optional[datetime], Optional[StaffRole]]:
        """Resolve target -> (department_id, patient_id, start, end, required_role)."""
        now = utc_now()
        if assignment_type == StaffAssignmentType.SURGERY:
            if surgery_id is None:
                raise DomainValidationError("surgeryId is required for a SURGERY assignment")
            surgery = self.surgery_repo.get_by_id(surgery_id)
            if not surgery:
                raise NotFoundError(f"Surgery with id {surgery_id} not found")
            if surgery.status in (SurgeryStatus.COMPLETED, SurgeryStatus.CANCELLED):
                raise ConflictError(f"Surgery {surgery_id} is {surgery.status.value}")
            start, end = now, None
            if surgery.slot_id is not None:
                slot = self.slot_repo.get_by_id(surgery.slot_id)
                if slot:
                    start, end = slot.start_time, slot.end_time
            return surgery.department_id, surgery.patient_id, start, end, surgery.required_staff_role
        if patient_id is None:
            raise DomainValidationError("patientId is required for a PATIENT assignment")
        patient = self.patient_repo.get_by_id(patient_id)
        if not patient:
            raise NotFoundError(f"Patient with id {patient_id} not found")
        PatientPolicy.validate_active(patient)
        if patient.current_department_id is None:
            raise ConflictError(f"Patient {patient_id} is not currently in a department")
        return patient.current_department_id, patient_id, now, None, None

    def assign_staff(
        self,
        staff_id: int,
        assignment_type: StaffAssignmentType,
        surgery_id: Optional[int] = None,
        patient_id: Optional[int] = None,
        required_role: Optional[StaffRole] = None,
        notes: str = "",
        actor: Actor = SYSTEM_ACTOR,
        source: EventSource = EventSource.MANUAL,
    ) -> StaffAssignment:
        """The single validated assignment workflow (used by manual calls AND matching)."""
        with self.transaction() as outbox:
            staff = self._require_staff(staff_id)
            department_id, target_patient_id, start, end, role_from_target = self.assignment_window(
                assignment_type, surgery_id, patient_id
            )
            effective_role = required_role or role_from_target
            has_active = self.assignment_repo.get_active_for_staff(staff_id) is not None
            StaffPolicy.validate_assignment(staff, effective_role, department_id, start, end, has_active)

            # Atomic claim: AVAILABLE -> ASSIGNED
            if not self.staff_repo.set_status_if(staff_id, StaffStatus.AVAILABLE, StaffStatus.ASSIGNED):
                raise ConflictError(f"Staff {staff.name} was assigned by another operation")
            assignment = self.assignment_repo.create(
                StaffAssignment(
                    id=None,
                    staff_id=staff_id,
                    assignment_type=assignment_type,
                    department_id=department_id,
                    start_time=start,
                    end_time=end,
                    surgery_id=surgery_id if assignment_type == StaffAssignmentType.SURGERY else None,
                    patient_id=target_patient_id if assignment_type == StaffAssignmentType.PATIENT else None,
                )
            )
            self.audit.record(
                FlowEventType.STAFF_ASSIGNED,
                actor=actor,
                source=source,
                patient_id=target_patient_id,
                resource_type=ResourceType.STAFF,
                resource_id=staff_id,
                department_id=department_id,
                previous_state=StaffStatus.AVAILABLE.value,
                new_state=StaffStatus.ASSIGNED.value,
                notes=notes or f"{staff.name} assigned to {assignment_type.value.lower()}",
                metadata={"assignmentId": assignment.id, "surgeryId": surgery_id, "patientId": target_patient_id},
            )
            self._fulfil_staff_waitlist(target_patient_id, staff, surgery_id, actor, source, outbox)
            outbox.add("STAFF_UPDATED", ResourceType.STAFF, staff_id, actor, source,
                       patient_id=target_patient_id, department_id=department_id,
                       previous_state=StaffStatus.AVAILABLE.value, new_state=StaffStatus.ASSIGNED.value)
        return assignment

    def _fulfil_staff_waitlist(self, patient_id, staff: Staff, surgery_id, actor, source, outbox: Outbox) -> None:
        entry = self.waitlist_repo.find_waiting_for_patient(patient_id, WaitlistResourceType.STAFF, surgery_id)
        if entry is None or (entry.required_staff_role is not None and entry.required_staff_role != staff.role):
            return
        if self.waitlist_repo.resolve_if_waiting(entry.id, WaitlistStatus.FULFILLED, utc_now(), staff.id):
            self.audit.record(
                FlowEventType.WAITLIST_FULFILLED, actor=actor, source=source, patient_id=patient_id,
                resource_type=ResourceType.WAITLIST_ENTRY, resource_id=entry.id, department_id=entry.department_id,
                previous_state=WaitlistStatus.WAITING.value, new_state=WaitlistStatus.FULFILLED.value,
                notes=f"Staff {staff.name} assigned", metadata={"staffId": staff.id},
            )
            outbox.add("WAITLIST_UPDATED", ResourceType.WAITLIST_ENTRY, entry.id, actor, source,
                       patient_id=patient_id, department_id=entry.department_id,
                       previous_state=WaitlistStatus.WAITING.value, new_state=WaitlistStatus.FULFILLED.value)

    def release_assignment(self, assignment_id: int, notes: str = "", actor: Actor = SYSTEM_ACTOR) -> StaffAssignment:
        with self.transaction() as outbox:
            assignment = self.assignment_repo.get_by_id(assignment_id)
            if not assignment:
                raise NotFoundError(f"Staff assignment with id {assignment_id} not found")
            if assignment.status != StaffAssignmentStatus.ACTIVE:
                raise ConflictError(f"Staff assignment {assignment_id} is already released")
            self.release_assignment_in_transaction(assignment, notes, actor, EventSource.MANUAL, outbox)
            updated = self.assignment_repo.get_by_id(assignment_id)
        return updated

    def release_assignment_in_transaction(
        self, assignment: StaffAssignment, notes: str, actor: Actor, source: EventSource, outbox: Outbox
    ) -> None:
        """Release without committing (caller owns the transaction)."""
        now = utc_now()
        if not self.assignment_repo.release_if_active(assignment.id, now):
            raise ConflictError(f"Staff assignment {assignment.id} changed state during release")
        staff = self._require_staff(assignment.staff_id)
        if not self.staff_repo.set_status_if(assignment.staff_id, StaffStatus.ASSIGNED, StaffStatus.AVAILABLE):
            raise ConflictError(f"Staff {staff.name} is not ASSIGNED; cannot release")
        self.audit.record(
            FlowEventType.STAFF_RELEASED,
            actor=actor,
            source=source,
            patient_id=assignment.patient_id,
            resource_type=ResourceType.STAFF,
            resource_id=assignment.staff_id,
            department_id=assignment.department_id,
            previous_state=StaffStatus.ASSIGNED.value,
            new_state=StaffStatus.AVAILABLE.value,
            notes=notes or f"{staff.name} released",
            metadata={"assignmentId": assignment.id, "surgeryId": assignment.surgery_id},
        )
        outbox.add("STAFF_UPDATED", ResourceType.STAFF, assignment.staff_id, actor, source,
                   patient_id=assignment.patient_id, department_id=assignment.department_id,
                   previous_state=StaffStatus.ASSIGNED.value, new_state=StaffStatus.AVAILABLE.value)
