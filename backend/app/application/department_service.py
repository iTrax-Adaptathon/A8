from typing import List, Optional

from app.application.audit_service import AuditService, TransactionalService
from app.domain.entities import Actor, Department, SYSTEM_ACTOR
from app.domain.enums import BedStatus, FlowEventType, ResourceType, TheatreStatus
from app.domain.policies import ConflictError, NotFoundError
from app.infrastructure.repositories import (
    BedRepository,
    DepartmentRepository,
    FlowEventRepository,
    TheatreRepository,
)
from app.realtime.event_bus import EventBus


class DepartmentService(TransactionalService):
    def __init__(
        self,
        department_repo: DepartmentRepository,
        bed_repo: Optional[BedRepository] = None,
        theatre_repo: Optional[TheatreRepository] = None,
        flow_event_repo: Optional[FlowEventRepository] = None,
        event_bus: Optional[EventBus] = None,
    ):
        db = department_repo.db
        super().__init__(db, AuditService(flow_event_repo or FlowEventRepository(db)), event_bus)
        self.department_repo = department_repo
        self.bed_repo = bed_repo or BedRepository(db)
        self.theatre_repo = theatre_repo or TheatreRepository(db)

    def create_department(self, department: Department, actor: Actor = SYSTEM_ACTOR) -> Department:
        with self.transaction() as outbox:
            created = self.department_repo.create(department)
            self.audit.record(
                FlowEventType.RESOURCE_CREATED,
                actor=actor,
                resource_type=ResourceType.DEPARTMENT,
                resource_id=created.id,
                department_id=created.id,
                new_state="ACTIVE",
                notes=f"Department {created.code} created",
            )
            outbox.add("DEPARTMENT_UPDATED", ResourceType.DEPARTMENT, created.id, actor,
                       department_id=created.id, new_state="ACTIVE")
        return created

    def get_department(self, department_id: int) -> Optional[Department]:
        return self.department_repo.get_by_id(department_id)

    def list_departments(self, include_inactive: bool = False, limit: Optional[int] = None, offset: int = 0) -> List[Department]:
        return self.department_repo.get_all(include_inactive=include_inactive, limit=limit, offset=offset)

    def count_departments(self, include_inactive: bool = False) -> int:
        return self.department_repo.count(include_inactive=include_inactive)

    def deactivate_department(self, department_id: int, notes: str = "", actor: Actor = SYSTEM_ACTOR) -> Department:
        """Soft delete. Refused while any bed is occupied or a theatre is in use.
        Beds and theatres of the department are deactivated too; history is untouched."""
        with self.transaction() as outbox:
            department = self.department_repo.get_by_id(department_id)
            if not department:
                raise NotFoundError(f"Department with id {department_id} not found")
            if not department.is_active:
                raise ConflictError(f"Department {department.name} is already inactive")
            counts = self.department_repo.bed_status_counts(department_id)
            if counts[BedStatus.OCCUPIED.value] > 0:
                raise ConflictError(
                    f"Department {department.name} has {counts[BedStatus.OCCUPIED.value]} occupied bed(s) and cannot be deactivated"
                )
            in_use = self.theatre_repo.count(department_id=department_id, status=TheatreStatus.IN_USE)
            if in_use > 0:
                raise ConflictError(f"Department {department.name} has a theatre in use and cannot be deactivated")

            beds_off = self.bed_repo.deactivate_by_department(department_id)
            theatres_off = self.theatre_repo.deactivate_by_department(department_id)
            self.department_repo.set_active(department_id, False)
            self.audit.record(
                FlowEventType.RESOURCE_DEACTIVATED,
                actor=actor,
                resource_type=ResourceType.DEPARTMENT,
                resource_id=department_id,
                department_id=department_id,
                previous_state="ACTIVE",
                new_state="INACTIVE",
                notes=notes or f"Department {department.code} deactivated",
                metadata={"bedsDeactivated": beds_off, "theatresDeactivated": theatres_off},
            )
            outbox.add("DEPARTMENT_UPDATED", ResourceType.DEPARTMENT, department_id, actor,
                       department_id=department_id, previous_state="ACTIVE", new_state="INACTIVE")
            updated = self.department_repo.get_by_id(department_id)
        return updated
