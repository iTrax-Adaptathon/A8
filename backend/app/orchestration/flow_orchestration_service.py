from datetime import datetime, timezone
from typing import Optional
from app.infrastructure.repositories import (
    PatientRepository,
    BedRepository,
    DepartmentRepository,
    FlowEventRepository,
)
from app.domain.entities import Patient, Bed, FlowEvent
from app.domain.enums import PatientStatus, BedStatus, FlowEventType
from app.domain.policies import PatientPolicy, BedPolicy, DomainValidationError


class FlowOrchestrationService:
    def __init__(
        self,
        patient_repo: PatientRepository,
        bed_repo: BedRepository,
        department_repo: DepartmentRepository,
        flow_event_repo: FlowEventRepository,
    ):
        self.patient_repo = patient_repo
        self.bed_repo = bed_repo
        self.department_repo = department_repo
        self.flow_event_repo = flow_event_repo

    def admit_patient(
        self,
        patient_id: int,
        department_id: int,
        bed_id: int,
        notes: str = "Patient admitted",
    ) -> Patient:
        patient = self.patient_repo.get_by_id(patient_id)
        if not patient:
            raise DomainValidationError(f"Patient with id {patient_id} not found")

        bed = self.bed_repo.get_by_id(bed_id)
        if not bed:
            raise DomainValidationError(f"Bed with id {bed_id} not found")

        department = self.department_repo.get_by_id(department_id)
        if not department:
            raise DomainValidationError(f"Department with id {department_id} not found")

        if bed.department_id != department_id:
            raise DomainValidationError(f"Bed {bed.bed_number} does not belong to department {department.name}")

        # Validate state transition & bed availability
        PatientPolicy.validate_transition(patient.current_status, PatientStatus.ADMITTED)
        BedPolicy.validate_assignment(bed.status)

        now = datetime.now(timezone.utc)

        # 1. Update Bed
        bed.status = BedStatus.OCCUPIED
        bed.current_patient_id = patient_id
        self.bed_repo.update(bed)

        # 2. Update Patient
        patient.current_status = PatientStatus.ADMITTED
        patient.current_department_id = department_id
        patient.current_bed_id = bed_id
        patient.admitted_at = now
        updated_patient = self.patient_repo.update(patient)

        # 3. Create Flow Event
        event = FlowEvent(
            id=None,
            event_type=FlowEventType.ADMISSION,
            patient_id=patient_id,
            to_department_id=department_id,
            to_bed_id=bed_id,
            timestamp=now,
            notes=notes,
        )
        self.flow_event_repo.create(event)

        return updated_patient

    def transfer_patient(
        self,
        patient_id: int,
        target_department_id: int,
        target_bed_id: int,
        notes: str = "Patient transferred",
    ) -> Patient:
        patient = self.patient_repo.get_by_id(patient_id)
        if not patient:
            raise DomainValidationError(f"Patient with id {patient_id} not found")

        if patient.current_status not in (PatientStatus.ADMITTED, PatientStatus.TRANSFERRED):
            raise DomainValidationError(f"Patient {patient_id} is not currently admitted (status: {patient.current_status.value})")

        target_bed = self.bed_repo.get_by_id(target_bed_id)
        if not target_bed:
            raise DomainValidationError(f"Target bed with id {target_bed_id} not found")

        target_department = self.department_repo.get_by_id(target_department_id)
        if not target_department:
            raise DomainValidationError(f"Target department with id {target_department_id} not found")

        if target_bed.department_id != target_department_id:
            raise DomainValidationError(f"Target bed {target_bed.bed_number} does not belong to department {target_department.name}")

        # Validate target bed availability
        BedPolicy.validate_assignment(target_bed.status)
        PatientPolicy.validate_transition(patient.current_status, PatientStatus.TRANSFERRED)

        now = datetime.now(timezone.utc)

        from_dept_id = patient.current_department_id
        from_bed_id = patient.current_bed_id

        # 1. Release previous bed
        if from_bed_id:
            old_bed = self.bed_repo.get_by_id(from_bed_id)
            if old_bed:
                old_bed.status = BedStatus.CLEANING
                old_bed.current_patient_id = None
                self.bed_repo.update(old_bed)

        # 2. Occupy new bed
        target_bed.status = BedStatus.OCCUPIED
        target_bed.current_patient_id = patient_id
        self.bed_repo.update(target_bed)

        # 3. Update Patient
        patient.current_status = PatientStatus.TRANSFERRED
        patient.current_department_id = target_department_id
        patient.current_bed_id = target_bed_id
        updated_patient = self.patient_repo.update(patient)

        # 4. Create Flow Event
        event = FlowEvent(
            id=None,
            event_type=FlowEventType.TRANSFER,
            patient_id=patient_id,
            from_department_id=from_dept_id,
            to_department_id=target_department_id,
            from_bed_id=from_bed_id,
            to_bed_id=target_bed_id,
            timestamp=now,
            notes=notes,
        )
        self.flow_event_repo.create(event)

        return updated_patient

    def discharge_patient(
        self,
        patient_id: int,
        notes: str = "Patient discharged",
    ) -> Patient:
        patient = self.patient_repo.get_by_id(patient_id)
        if not patient:
            raise DomainValidationError(f"Patient with id {patient_id} not found")

        if patient.current_status in (PatientStatus.REGISTERED, PatientStatus.DISCHARGED):
            raise DomainValidationError(f"Patient {patient_id} cannot be discharged from status {patient.current_status.value}")

        PatientPolicy.validate_transition(patient.current_status, PatientStatus.DISCHARGED)
        now = datetime.now(timezone.utc)

        from_dept_id = patient.current_department_id
        from_bed_id = patient.current_bed_id

        # 1. Release bed
        if from_bed_id:
            bed = self.bed_repo.get_by_id(from_bed_id)
            if bed:
                bed.status = BedStatus.AVAILABLE
                bed.current_patient_id = None
                self.bed_repo.update(bed)

        # 2. Update Patient
        patient.current_status = PatientStatus.DISCHARGED
        patient.current_bed_id = None
        patient.discharged_at = now
        updated_patient = self.patient_repo.update(patient)

        # 3. Create Flow Event
        event = FlowEvent(
            id=None,
            event_type=FlowEventType.DISCHARGE,
            patient_id=patient_id,
            from_department_id=from_dept_id,
            from_bed_id=from_bed_id,
            timestamp=now,
            notes=notes,
        )
        self.flow_event_repo.create(event)

        return updated_patient
