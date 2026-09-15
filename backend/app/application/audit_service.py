"""Audit trail + transactional helpers shared by every service.

AuditService.record() appends an immutable FlowEvent inside the caller's
transaction. TransactionalService.transaction() commits the unit of work and
only then publishes the collected realtime events.
"""
from contextlib import contextmanager
from typing import Any, Dict, List, Optional

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.domain.entities import Actor, FlowEvent, SYSTEM_ACTOR
from app.domain.enums import EventSource, FlowEventType, ResourceType
from app.domain.policies import ConflictError, utc_now
from app.infrastructure.repositories import FlowEventRepository
from app.realtime.event_bus import EventBus, RealtimeEvent, event_bus as default_event_bus


class AuditService:
    def __init__(self, flow_event_repo: FlowEventRepository):
        self.flow_event_repo = flow_event_repo

    def record(
        self,
        event_type: FlowEventType,
        actor: Actor = SYSTEM_ACTOR,
        source: EventSource = EventSource.MANUAL,
        patient_id: Optional[int] = None,
        resource_type: Optional[ResourceType] = None,
        resource_id: Optional[int] = None,
        department_id: Optional[int] = None,
        previous_state: Optional[str] = None,
        new_state: Optional[str] = None,
        notes: str = "",
        metadata: Optional[Dict[str, Any]] = None,
        from_department_id: Optional[int] = None,
        to_department_id: Optional[int] = None,
        from_bed_id: Optional[int] = None,
        to_bed_id: Optional[int] = None,
    ) -> FlowEvent:
        event = FlowEvent(
            id=None,
            event_type=event_type,
            timestamp=utc_now(),
            patient_id=patient_id,
            from_department_id=from_department_id,
            to_department_id=to_department_id,
            from_bed_id=from_bed_id,
            to_bed_id=to_bed_id,
            notes=notes or "",
            resource_type=resource_type,
            resource_id=resource_id,
            department_id=department_id,
            previous_state=previous_state,
            new_state=new_state,
            actor_id=actor.id,
            actor_name=actor.name,
            source=source,
            metadata=metadata or {},
        )
        return self.flow_event_repo.create(event)


class Outbox:
    """Realtime events collected during a transaction; delivered after commit."""

    def __init__(self):
        self.events: List[RealtimeEvent] = []

    def add(
        self,
        event_type: str,
        resource_type: ResourceType,
        resource_id: Optional[int],
        actor: Actor,
        source: EventSource = EventSource.MANUAL,
        patient_id: Optional[int] = None,
        department_id: Optional[int] = None,
        previous_state: Optional[str] = None,
        new_state: Optional[str] = None,
    ) -> None:
        self.events.append(
            RealtimeEvent(
                type=event_type,
                resource_type=resource_type.value,
                resource_id=resource_id,
                patient_id=patient_id,
                department_id=department_id,
                previous_state=previous_state,
                new_state=new_state,
                actor_id=actor.id,
                source=source.value,
            )
        )


class TransactionalService:
    """Base for services that mutate state.

    Usage::

        with self.transaction() as outbox:
            ... validate, mutate via repositories (flush only) ...
            outbox.add(...)
        # here the transaction is committed and events were published
    """

    def __init__(self, db: Session, audit: AuditService, event_bus: Optional[EventBus] = None):
        self.db = db
        self.audit = audit
        self.event_bus = event_bus or default_event_bus

    @contextmanager
    def transaction(self):
        outbox = Outbox()
        try:
            yield outbox
            self.db.commit()
        except IntegrityError as exc:
            self.db.rollback()
            raise ConflictError(
                f"Operation rejected by a database integrity constraint: {_constraint_message(exc)}"
            ) from exc
        except Exception:
            self.db.rollback()
            raise
        # Only reached after a successful commit.
        self.event_bus.publish(outbox.events)


def _constraint_message(exc: IntegrityError) -> str:
    return str(exc.orig) if getattr(exc, "orig", None) is not None else str(exc)
