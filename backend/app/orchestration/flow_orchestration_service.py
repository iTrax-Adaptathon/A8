"""Patient flow workflows: admission, transfer, discharge and bed release.

Every workflow is ONE database transaction. Bed and patient claims are
performed with atomic compare-and-set UPDATE statements (see the repositories),
so two concurrent requests for the same bed can never both succeed: the loser
gets a ConflictError (HTTP 409) and its transaction is rolled back.

Bed lifecycle around a patient:

    AVAILABLE --admit/transfer--> OCCUPIED --transfer/discharge--> CLEANING
    CLEANING --POST /beds/{id}/release--> AVAILABLE
"""
from typing import Optional

from sqlalchemy.orm import Session

from app.application.audit_service import AuditService, TransactionalService
from app.domain.entities import Actor, Bed, Patient, SYSTEM_ACTOR
from app.domain.enums import (
    BedStatus,
    EventSource,
    FlowEventType,
    PatientStatus,
    ResourceType,
    WaitlistResourceType,
    WaitlistStatus,
)
from app.domain.policies import (
    BedPolicy,
    ConflictError,
    NotFoundError,
    PatientPolicy,
    utc_now,
)
from app.infrastructure.repositories import (
    BedRepository,
    DepartmentRepository,
    FlowEventRepository,
    PatientRepository,
    WaitlistRepository,
)
from app.realtime.event_bus import EventBus


class FlowOrchestrationService(TransactionalService):
    def __init__(
        self,
        patient_repo: PatientRepository,
        bed_repo: BedRepository,
        department_repo: DepartmentRepository,
        flow_event_repo: FlowEventRepository,
        waitlist_repo: Optional[WaitlistRepository] = None,
        event_bus: Optional[EventBus] = None,
    ):
        db: Session = patient_repo.db
        super().__init__(db, AuditService(flow_event_repo), event_bus)
        self.patient_repo = patient_repo
        self.bed_repo = bed_repo
        self.department_repo = department_repo
        self.flow_event_repo = flow_event_repo
        self.waitlist_repo = waitlist_repo or WaitlistRepository(db)

    # ------------------------------------------------------------------
    # Lookups
    # ------------------------------------------------------------------
    def _get_patient(self, patient_id: int) -> Patient:
        patient = self.patient_repo.get_by_id(patient_id)
        if not patient:
            raise NotFoundError(f"Patient with id {patient_id} not found")
        return patient

    def _get_bed(self, bed_id: int, label: str = "Bed") -> Bed:
        bed = self.bed_repo.get_by_id(bed_id)
        if not bed:
            raise NotFoundError(f"{label} with id {bed_id} not found")
        return bed

    def _get_department(self, department_id: int, label: str = "Department"):
        department = self.department_repo.get_by_id(department_id)
        if not department:
            raise NotFoundError(f"{label} with id {department_id} not found")
        if not department.is_active:
            raise ConflictError(f"{label} {department.name} is inactive")
        return department

    def _fulfil_bed_waitlist(self, patient_id: int, bed: Bed, actor: Actor, source: EventSource, now, outbox) -> None:
        """A patient who just received a bed no longer waits for one in that department."""
        entry = self.waitlist_repo.find_waiting_for_patient(patient_id, WaitlistResourceType.BED)
        while entry is not None:
            if entry.department_id != bed.department_id:
                break
            if self.waitlist_repo.resolve_if_waiting(entry.id, WaitlistStatus.FULFILLED, now, bed.id):
                self.audit.record(
                    FlowEventType.WAITLIST_FULFILLED,
                    actor=actor,
                    source=source,
                    patient_id=patient_id,
                    resource_type=ResourceType.WAITLIST_ENTRY,
                    resource_id=entry.id,
                    department_id=entry.department_id,
                    previous_state=WaitlistStatus.WAITING.value,
                    new_state=WaitlistStatus.FULFILLED.value,
                    notes=f"Bed {bed.bed_number} assigned",
                    metadata={"bedId": bed.id},
                )
                outbox.add(
                    "WAITLIST_UPDATED", ResourceType.WAITLIST_ENTRY, entry.id, actor, source,
                    patient_id=patient_id, department_id=entry.department_id,
                    previous_state=WaitlistStatus.WAITING.value, new_state=WaitlistStatus.FULFILLED.value,
                )
            entry = self.waitlist_repo.find_waiting_for_patient(patient_id, WaitlistResourceType.BED)

    # ------------------------------------------------------------------
    # Admission
    # ------------------------------------------------------------------
    def admit_patient(
        self,
        patient_id: int,
        department_id: int,
        bed_id: int,
        notes: str = "Patient admitted",
        actor: Actor = SYSTEM_ACTOR,
        source: EventSource = EventSource.MANUAL,
    ) -> Patient:
        with self.transaction() as outbox:
            patient = self._get_patient(patient_id)
            bed = self._get_bed(bed_id)
            department = self._get_department(department_id)

            if bed.department_id != department_id:
                raise ConflictError(f"Bed {bed.bed_number} does not belong to department {department.name}")

            # Validate state transition & bed availability (fast, readable failures)
            PatientPolicy.validate_admittable(patient)
            PatientPolicy.validate_transition(patient.current_status, PatientStatus.ADMITTED)
            BedPolicy.validate_assignment(bed.status, bed.is_active, bed.current_patient_id)

            now = utc_now()

            # 1. Claim the bed atomically (status + patient in ONE statement).
            if not self.bed_repo.claim_for_patient(bed_id, patient_id):
                raise ConflictError(f"Bed {bed.bed_number} was assigned by another operation")

            # 2. Link the patient atomically (fails if the patient changed meanwhile).
            if not self.patient_repo.link_bed(
                patient_id,
                bed_id,
                department_id,
                PatientStatus.ADMITTED,
                expected_statuses=[PatientStatus.REGISTERED],
                expected_bed_id=None,
                admitted_at=now,
            ):
                raise ConflictError(f"Patient {patient_id} was modified by another operation")

            # 3. Audit
            self.audit.record(
                FlowEventType.ADMISSION,
                actor=actor,
                source=source,
                patient_id=patient_id,
                resource_type=ResourceType.BED,
                resource_id=bed_id,
                department_id=department_id,
                previous_state=PatientStatus.REGISTERED.value,
                new_state=PatientStatus.ADMITTED.value,
                notes=notes,
                to_department_id=department_id,
                to_bed_id=bed_id,
                metadata={"bedPreviousState": BedStatus.AVAILABLE.value, "bedNewState": BedStatus.OCCUPIED.value},
            )
            self._fulfil_bed_waitlist(patient_id, bed, actor, source, now, outbox)

            outbox.add("PATIENT_UPDATED", ResourceType.PATIENT, patient_id, actor, source,
                       patient_id=patient_id, department_id=department_id,
                       previous_state=PatientStatus.REGISTERED.value, new_state=PatientStatus.ADMITTED.value)
            outbox.add("BED_UPDATED", ResourceType.BED, bed_id, actor, source,
                       patient_id=patient_id, department_id=department_id,
                       previous_state=BedStatus.AVAILABLE.value, new_state=BedStatus.OCCUPIED.value)
            updated_patient = self._get_patient(patient_id)
        return updated_patient

    # ------------------------------------------------------------------
    # Transfer
    # ------------------------------------------------------------------
    def transfer_patient(
        self,
        patient_id: int,
        target_department_id: int,
        target_bed_id: int,
        notes: str = "Patient transferred",
        actor: Actor = SYSTEM_ACTOR,
        source: EventSource = EventSource.MANUAL,
    ) -> Patient:
        with self.transaction() as outbox:
            patient = self._get_patient(patient_id)
            PatientPolicy.validate_transferable(patient)

            target_bed = self._get_bed(target_bed_id, "Target bed")
            target_department = self._get_department(target_department_id, "Target department")

            if target_bed.department_id != target_department_id:
                raise ConflictError(
                    f"Target bed {target_bed.bed_number} does not belong to department {target_department.name}"
                )
            if target_bed_id == patient.current_bed_id:
                raise ConflictError(f"Patient {patient_id} already occupies bed {target_bed.bed_number}")

            BedPolicy.validate_assignment(target_bed.status, target_bed.is_active, target_bed.current_patient_id)
            PatientPolicy.validate_transition(patient.current_status, PatientStatus.TRANSFERRED)

            now = utc_now()
            from_dept_id = patient.current_department_id
            from_bed_id = patient.current_bed_id
            previous_status = patient.current_status

            # 1. Release the previous bed (OCCUPIED -> CLEANING) in one statement.
            if from_bed_id is not None:
                if not self.bed_repo.release_from_patient(from_bed_id, patient_id, BedStatus.CLEANING):
                    raise ConflictError(f"Bed {from_bed_id} is no longer occupied by patient {patient_id}")

            # 2. Claim the new bed atomically.
            if not self.bed_repo.claim_for_patient(target_bed_id, patient_id):
                raise ConflictError(f"Bed {target_bed.bed_number} was assigned by another operation")

            # 3. Move the patient (single UPDATE guarded by the expected old bed).
            if not self.patient_repo.link_bed(
                patient_id,
                target_bed_id,
                target_department_id,
                PatientStatus.TRANSFERRED,
                expected_statuses=[PatientStatus.ADMITTED, PatientStatus.TRANSFERRED],
                expected_bed_id=from_bed_id,
            ):
                raise ConflictError(f"Patient {patient_id} was modified by another operation")

            # 4. Audit
            self.audit.record(
                FlowEventType.TRANSFER,
                actor=actor,
                source=source,
                patient_id=patient_id,
                resource_type=ResourceType.BED,
                resource_id=target_bed_id,
                department_id=target_department_id,
                previous_state=previous_status.value,
                new_state=PatientStatus.TRANSFERRED.value,
                notes=notes,
                from_department_id=from_dept_id,
                to_department_id=target_department_id,
                from_bed_id=from_bed_id,
                to_bed_id=target_bed_id,
            )
            if from_bed_id is not None:
                self.audit.record(
                    FlowEventType.BED_RELEASE,
                    actor=actor,
                    source=source,
                    patient_id=patient_id,
                    resource_type=ResourceType.BED,
                    resource_id=from_bed_id,
                    department_id=from_dept_id,
                    previous_state=BedStatus.OCCUPIED.value,
                    new_state=BedStatus.CLEANING.value,
                    notes="Released on transfer",
                    from_bed_id=from_bed_id,
                )
                outbox.add("BED_UPDATED", ResourceType.BED, from_bed_id, actor, source,
                           patient_id=patient_id, department_id=from_dept_id,
                           previous_state=BedStatus.OCCUPIED.value, new_state=BedStatus.CLEANING.value)
            self._fulfil_bed_waitlist(patient_id, target_bed, actor, source, now, outbox)

            outbox.add("BED_UPDATED", ResourceType.BED, target_bed_id, actor, source,
                       patient_id=patient_id, department_id=target_department_id,
                       previous_state=BedStatus.AVAILABLE.value, new_state=BedStatus.OCCUPIED.value)
            outbox.add("PATIENT_UPDATED", ResourceType.PATIENT, patient_id, actor, source,
                       patient_id=patient_id, department_id=target_department_id,
                       previous_state=previous_status.value, new_state=PatientStatus.TRANSFERRED.value)
            updated_patient = self._get_patient(patient_id)
        return updated_patient

    # ------------------------------------------------------------------
    # Discharge
    # ------------------------------------------------------------------
    def discharge_patient(
        self,
        patient_id: int,
        notes: str = "Patient discharged",
        actor: Actor = SYSTEM_ACTOR,
        source: EventSource = EventSource.MANUAL,
    ) -> Patient:
        with self.transaction() as outbox:
            patient = self._get_patient(patient_id)
            PatientPolicy.validate_dischargeable(patient)
            PatientPolicy.validate_transition(patient.current_status, PatientStatus.DISCHARGED)

            now = utc_now()
            from_dept_id = patient.current_department_id
            from_bed_id = patient.current_bed_id
            previous_status = patient.current_status

            # 1. Release bed (OCCUPIED -> CLEANING). Never straight to AVAILABLE.
            if from_bed_id is not None:
                if not self.bed_repo.release_from_patient(from_bed_id, patient_id, BedStatus.CLEANING):
                    raise ConflictError(f"Bed {from_bed_id} is no longer occupied by patient {patient_id}")

            # 2. Update patient atomically
            if not self.patient_repo.unlink_bed_for_discharge(patient_id, from_bed_id, now):
                raise ConflictError(f"Patient {patient_id} was modified by another operation")

            # 3. Any open bed requests for this patient are void now.
            entry = self.waitlist_repo.find_waiting_for_patient(patient_id, WaitlistResourceType.BED)
            while entry is not None:
                self.waitlist_repo.resolve_if_waiting(entry.id, WaitlistStatus.CANCELLED)
                self.audit.record(
                    FlowEventType.WAITLIST_REMOVED, actor=actor, source=source, patient_id=patient_id,
                    resource_type=ResourceType.WAITLIST_ENTRY, resource_id=entry.id,
                    department_id=entry.department_id, previous_state=WaitlistStatus.WAITING.value,
                    new_state=WaitlistStatus.CANCELLED.value, notes="Patient discharged",
                )
                entry = self.waitlist_repo.find_waiting_for_patient(patient_id, WaitlistResourceType.BED)

            # 4. Audit
            self.audit.record(
                FlowEventType.DISCHARGE,
                actor=actor,
                source=source,
                patient_id=patient_id,
                resource_type=ResourceType.PATIENT,
                resource_id=patient_id,
                department_id=from_dept_id,
                previous_state=previous_status.value,
                new_state=PatientStatus.DISCHARGED.value,
                notes=notes,
                from_department_id=from_dept_id,
                from_bed_id=from_bed_id,
            )
            if from_bed_id is not None:
                self.audit.record(
                    FlowEventType.BED_RELEASE,
                    actor=actor,
                    source=source,
                    patient_id=patient_id,
                    resource_type=ResourceType.BED,
                    resource_id=from_bed_id,
                    department_id=from_dept_id,
                    previous_state=BedStatus.OCCUPIED.value,
                    new_state=BedStatus.CLEANING.value,
                    notes="Released on discharge",
                    from_bed_id=from_bed_id,
                )
                outbox.add("BED_UPDATED", ResourceType.BED, from_bed_id, actor, source,
                           patient_id=patient_id, department_id=from_dept_id,
                           previous_state=BedStatus.OCCUPIED.value, new_state=BedStatus.CLEANING.value)
            outbox.add("PATIENT_UPDATED", ResourceType.PATIENT, patient_id, actor, source,
                       patient_id=patient_id, department_id=from_dept_id,
                       previous_state=previous_status.value, new_state=PatientStatus.DISCHARGED.value)
            updated_patient = self._get_patient(patient_id)
        return updated_patient

    # ------------------------------------------------------------------
    # Bed release: CLEANING -> AVAILABLE (the only way a bed becomes assignable again)
    # ------------------------------------------------------------------
    def release_bed(self, bed_id: int, notes: str = "Bed cleaned", actor: Actor = SYSTEM_ACTOR) -> Bed:
        with self.transaction() as outbox:
            bed = self._get_bed(bed_id)
            if not bed.is_active:
                raise ConflictError(f"Bed {bed.bed_number} is inactive")
            BedPolicy.validate_release(bed.status)
            if not self.bed_repo.set_status_if(bed_id, BedStatus.CLEANING, BedStatus.AVAILABLE):
                raise ConflictError(f"Bed {bed.bed_number} changed state during release")
            self.audit.record(
                FlowEventType.BED_STATUS_CHANGE,
                actor=actor,
                resource_type=ResourceType.BED,
                resource_id=bed_id,
                department_id=bed.department_id,
                previous_state=BedStatus.CLEANING.value,
                new_state=BedStatus.AVAILABLE.value,
                notes=notes,
            )
            outbox.add("BED_UPDATED", ResourceType.BED, bed_id, actor, department_id=bed.department_id,
                       previous_state=BedStatus.CLEANING.value, new_state=BedStatus.AVAILABLE.value)
            updated = self._get_bed(bed_id)
        return updated
