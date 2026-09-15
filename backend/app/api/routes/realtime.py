"""Realtime WebSocket: /api/v1/ws/capacity

Clients receive one small JSON message per committed state change:

    {
      "type": "BED_UPDATED",            # see README "Realtime" for the list
      "resourceType": "BED",
      "resourceId": 12,
      "patientId": 5,                   # nullable
      "departmentId": 2,                # nullable
      "previousState": "CLEANING",      # nullable
      "newState": "AVAILABLE",          # nullable
      "actorId": "nurse-7",
      "source": "MANUAL",               # MANUAL | AUTO_MATCH | SYSTEM
      "timestamp": "2026-09-15T10:00:00+00:00"
    }

Messages are emitted strictly after the database transaction has committed.
The frontend should re-fetch /capacity (or the affected resource) on receipt.
"""
from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from app.api.schemas.base import CamelModel
from app.realtime.event_bus import event_bus

router = APIRouter(tags=["Realtime"])


class RealtimeEventSchema(CamelModel):
    """Documentation of the WebSocket message format (not served over HTTP)."""

    type: str
    resource_type: str
    resource_id: int | None = None
    patient_id: int | None = None
    department_id: int | None = None
    previous_state: str | None = None
    new_state: str | None = None
    actor_id: str
    source: str
    timestamp: str


class RealtimeInfoSchema(CamelModel):
    websocket_path: str
    event_types: list[str]
    message_schema: dict
    connected_clients: int


REALTIME_EVENT_TYPES = [
    "PATIENT_UPDATED",
    "BED_UPDATED",
    "DEPARTMENT_UPDATED",
    "THEATRE_UPDATED",
    "THEATRE_SLOT_UPDATED",
    "SURGERY_UPDATED",
    "STAFF_UPDATED",
    "WAITLIST_UPDATED",
    "MATCH_ASSIGNED",
]


@router.get("/realtime", response_model=RealtimeInfoSchema, summary="Describe the realtime WebSocket contract")
def realtime_info():
    return RealtimeInfoSchema(
        websocket_path="/api/v1/ws/capacity",
        event_types=REALTIME_EVENT_TYPES,
        message_schema=RealtimeEventSchema.model_json_schema(by_alias=True),
        connected_clients=event_bus.manager.connection_count,
    )


@router.websocket("/ws/capacity")
async def capacity_websocket(websocket: WebSocket):
    await event_bus.manager.connect(websocket)
    try:
        while True:
            # Clients may send anything (e.g. "ping"); we only push events.
            await websocket.receive_text()
    except WebSocketDisconnect:
        pass
    finally:
        await event_bus.manager.disconnect(websocket)
