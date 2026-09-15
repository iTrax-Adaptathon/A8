"""Realtime broadcast bus.

Design rules (see README "Realtime"):

* Database correctness never depends on delivery. Services call
  ``event_bus.publish(...)`` strictly AFTER ``db.commit()`` has returned.
* ``publish`` never raises. Delivery problems are logged and swallowed.
* Events are small, flat JSON documents (``RealtimeEvent``).
"""
import asyncio
import logging
import threading
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Any, Callable, Dict, List, Optional, Set

from fastapi import WebSocket

logger = logging.getLogger(__name__)


@dataclass
class RealtimeEvent:
    type: str  # e.g. BED_UPDATED, PATIENT_UPDATED, MATCH_ASSIGNED
    resource_type: str
    resource_id: Optional[int] = None
    patient_id: Optional[int] = None
    department_id: Optional[int] = None
    previous_state: Optional[str] = None
    new_state: Optional[str] = None
    actor_id: str = "system"
    source: str = "MANUAL"
    timestamp: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    def to_payload(self) -> Dict[str, Any]:
        """camelCase wire format."""
        raw = asdict(self)
        return {
            "type": raw["type"],
            "resourceType": raw["resource_type"],
            "resourceId": raw["resource_id"],
            "patientId": raw["patient_id"],
            "departmentId": raw["department_id"],
            "previousState": raw["previous_state"],
            "newState": raw["new_state"],
            "actorId": raw["actor_id"],
            "source": raw["source"],
            "timestamp": raw["timestamp"],
        }


class ConnectionManager:
    def __init__(self):
        self._connections: Set[WebSocket] = set()
        self._lock = asyncio.Lock()

    async def connect(self, websocket: WebSocket) -> None:
        await websocket.accept()
        async with self._lock:
            self._connections.add(websocket)

    async def disconnect(self, websocket: WebSocket) -> None:
        async with self._lock:
            self._connections.discard(websocket)

    @property
    def connection_count(self) -> int:
        return len(self._connections)

    async def broadcast(self, payload: Dict[str, Any]) -> None:
        async with self._lock:
            targets = list(self._connections)
        for ws in targets:
            try:
                await ws.send_json(payload)
            except Exception as exc:  # a dead client must never affect others
                logger.debug("Dropping websocket client after send failure: %s", exc)
                await self.disconnect(ws)


class EventBus:
    """Fan-out of committed events to WebSocket clients and in-process subscribers."""

    def __init__(self):
        self.manager = ConnectionManager()
        self._loop: Optional[asyncio.AbstractEventLoop] = None
        self._subscribers: List[Callable[[RealtimeEvent], None]] = []
        self._sub_lock = threading.Lock()

    # -- lifecycle -------------------------------------------------------
    def bind_loop(self, loop: asyncio.AbstractEventLoop) -> None:
        self._loop = loop

    def unbind_loop(self) -> None:
        self._loop = None

    # -- in-process subscribers (used by tests and diagnostics) -----------
    def subscribe(self, callback: Callable[[RealtimeEvent], None]) -> None:
        with self._sub_lock:
            self._subscribers.append(callback)

    def unsubscribe(self, callback: Callable[[RealtimeEvent], None]) -> None:
        with self._sub_lock:
            if callback in self._subscribers:
                self._subscribers.remove(callback)

    # -- publishing --------------------------------------------------------
    def publish(self, events: List[RealtimeEvent]) -> None:
        """Deliver events. Must only be called after a successful commit.
        Never raises."""
        for event in events:
            try:
                self._publish_one(event)
            except Exception as exc:  # pragma: no cover - defensive
                logger.warning("Realtime publish failed for %s: %s", event.type, exc)

    def _publish_one(self, event: RealtimeEvent) -> None:
        with self._sub_lock:
            subscribers = list(self._subscribers)
        for callback in subscribers:
            try:
                callback(event)
            except Exception as exc:
                logger.warning("Realtime subscriber failed: %s", exc)

        loop = self._loop
        if loop is None or loop.is_closed():
            return
        payload = event.to_payload()
        try:
            running = asyncio.get_running_loop()
        except RuntimeError:
            running = None
        if running is loop:
            loop.create_task(self.manager.broadcast(payload))
        else:
            loop.call_soon_threadsafe(lambda: loop.create_task(self.manager.broadcast(payload)))


event_bus = EventBus()
