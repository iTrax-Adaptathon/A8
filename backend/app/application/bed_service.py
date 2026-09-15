from typing import List, Optional

from app.application.audit_service import AuditService, TransactionalService
from app.domain.entities import Actor, Bed, SYSTEM_ACTOR
from app.domain.enums import BedStatus, BedType, FlowEventType, ResourceType
from app.domain.policies import BedPolicy, ConflictError, DomainValidationError, NotFoundError
from app.infrastructure.repositories import BedRepository, DepartmentRepository, FlowEventRepository
from app.realtime.event_bus import EventBus


class BedService(TransactionalService):
    def __init__(
        self,
        bed_repo: BedRepository,
        department_repo: Optional[DepartmentRepository] = None,
        flow_event_repo: Optional[FlowEventRepository] = None,
        event_bus: Optional[EventBus] = None,
    ):
        db = bed_repo.db
        super().__init__(db, AuditService(flow_event_repo or FlowEventRepository(db)), event_bus)
        self.bed_repo = bed_repo
        self.department_repo = department_repo or DepartmentRepository(db)

    def _get_bed(self, bed_id: int) -> Bed:
        bed = self.bed_repo.get_by_id(bed_id)
        if not bed:
            raise NotFoundError(f"Bed with id {bed_id} not found")
        return bed

    def create_bed(self, bed: Bed, actor: Actor = SYSTEM_ACTOR) -> Bed:
        if bed.status == BedStatus.OCCUPIED:
            raise DomainValidationError("A bed cannot be created as OCCUPIED; admit a patient instead.")
        department = self.department_repo.get_by_id(bed.department_id)
        if not department:
            raise NotFoundError(f"Department with id {bed.department_id} not found")
        if not department.is_active:
            raise ConflictError(f"Department {department.name} is inactive")
        bed.current_patient_id = None
        with self.transaction() as outbox:
            created = self.bed_repo.create(bed)
            self.audit.record(
                FlowEventType.RESOURCE_CREATED,
                actor=actor,
                resource_type=ResourceType.BED,
                resource_id=created.id,
                department_id=created.department_id,
                new_state=created.status.value,
                notes=f"Bed {created.bed_number} created",
            )
            outbox.add("BED_UPDATED", ResourceType.BED, created.id, actor,
                       department_id=created.department_id, new_state=created.status.value)
        return created

    def get_bed(self, bed_id: int) -> Optional[Bed]:
        return self.bed_repo.get_by_id(bed_id)

    def list_beds(
        self,
        department_id: Optional[int] = None,
        status: Optional[BedStatus] = None,
        bed_type: Optional[BedType] = None,
        include_inactive: bool = False,
        limit: Optional[int] = None,
        offset: int = 0,
    ) -> List[Bed]:
        return self.bed_repo.get_all(
            department_id=department_id,
            status=status,
            bed_type=bed_type,
            include_inactive=include_inactive,
            limit=limit,
            offset=offset,
        )

    def count_beds(
        self,
        department_id: Optional[int] = None,
        status: Optional[BedStatus] = None,
        bed_type: Optional[BedType] = None,
        include_inactive: bool = False,
    ) -> int:
        return self.bed_repo.count(department_id, status, bed_type, include_inactive)

    def update_bed_status(self, bed_id: int, new_status: BedStatus, notes: str = "", actor: Actor = SYSTEM_ACTOR) -> Bed:
        """Manual status change between the non-occupied states only. An
        OCCUPIED bed can never be freed here (see BedPolicy)."""
        with self.transaction() as outbox:
            bed = self._get_bed(bed_id)
            if not bed.is_active:
                raise ConflictError(f"Bed {bed.bed_number} is inactive")
            BedPolicy.validate_status_transition(bed.status, new_status)
            if not self.bed_repo.set_status_if(bed_id, bed.status, new_status):
                raise ConflictError(f"Bed {bed.bed_number} changed state during the update")
            self.audit.record(
                FlowEventType.BED_STATUS_CHANGE,
                actor=actor,
                resource_type=ResourceType.BED,
                resource_id=bed_id,
                department_id=bed.department_id,
                previous_state=bed.status.value,
                new_state=new_status.value,
                notes=notes or f"Bed {bed.bed_number} status changed",
            )
            outbox.add("BED_UPDATED", ResourceType.BED, bed_id, actor, department_id=bed.department_id,
                       previous_state=bed.status.value, new_state=new_status.value)
            updated = self._get_bed(bed_id)
        return updated

    def deactivate_bed(self, bed_id: int, notes: str = "", actor: Actor = SYSTEM_ACTOR) -> Bed:
        with self.transaction() as outbox:
            bed = self._get_bed(bed_id)
            if not bed.is_active:
                raise ConflictError(f"Bed {bed.bed_number} is already inactive")
            BedPolicy.validate_deactivation(bed)
            bed.is_active = False
            updated = self.bed_repo.update(bed)
            self.audit.record(
                FlowEventType.RESOURCE_DEACTIVATED,
                actor=actor,
                resource_type=ResourceType.BED,
                resource_id=bed_id,
                department_id=bed.department_id,
                previous_state=bed.status.value,
                new_state="INACTIVE",
                notes=notes or f"Bed {bed.bed_number} deactivated",
            )
            outbox.add("BED_UPDATED", ResourceType.BED, bed_id, actor, department_id=bed.department_id,
                       previous_state=bed.status.value, new_state="INACTIVE")
        return updated
