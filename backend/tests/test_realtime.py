"""Realtime: events are emitted only after a successful commit; failed or
rolled-back operations emit nothing; broadcast problems never affect the DB."""
import logging

from app.realtime.event_bus import event_bus
from tests.helpers import ACTOR, admit, create_bed, create_department, create_patient, discharge, release_bed


def test_successful_mutation_emits_events(client, realtime_events):
    dept = create_department(client)
    bed = create_bed(client, dept["id"])
    patient = create_patient(client)
    realtime_events.clear()
    assert admit(client, patient["id"], dept["id"], bed["id"], headers=ACTOR).status_code == 200
    types = [(e.type, e.resource_type, e.resource_id) for e in realtime_events]
    assert ("PATIENT_UPDATED", "PATIENT", patient["id"]) in types
    assert ("BED_UPDATED", "BED", bed["id"]) in types
    bed_evt = next(e for e in realtime_events if e.type == "BED_UPDATED")
    assert bed_evt.previous_state == "AVAILABLE" and bed_evt.new_state == "OCCUPIED"
    assert bed_evt.actor_id == "nurse-7" and bed_evt.department_id == dept["id"] and bed_evt.patient_id == patient["id"]
    payload = bed_evt.to_payload()
    assert set(payload) == {"type", "resourceType", "resourceId", "patientId", "departmentId", "previousState", "newState", "actorId", "source", "timestamp"}


def test_failed_mutation_emits_nothing(client, realtime_events):
    dept = create_department(client)
    bed = create_bed(client, dept["id"])
    p1, p2 = create_patient(client), create_patient(client)
    admit(client, p1["id"], dept["id"], bed["id"])
    realtime_events.clear()
    assert admit(client, p2["id"], dept["id"], bed["id"]).status_code == 409
    assert client.patch(f"/api/v1/beds/{bed['id']}/status", json={"newStatus": "AVAILABLE"}).status_code == 409
    assert admit(client, 9999, dept["id"], bed["id"]).status_code == 404
    assert realtime_events == []


def test_websocket_receives_committed_events_only(client):
    dept = create_department(client)
    bed = create_bed(client, dept["id"])
    p1, p2 = create_patient(client), create_patient(client)
    with client.websocket_connect("/api/v1/ws/capacity") as ws:
        # a failing operation first: must not produce a message
        assert admit(client, p1["id"], 9999, bed["id"]).status_code == 404
        assert admit(client, p1["id"], dept["id"], bed["id"]).status_code == 200
        msg = ws.receive_json()
        assert msg["type"] in ("PATIENT_UPDATED", "BED_UPDATED")
        assert msg["patientId"] == p1["id"] and msg["source"] == "MANUAL"
        msg2 = ws.receive_json()
        assert {msg["type"], msg2["type"]} == {"PATIENT_UPDATED", "BED_UPDATED"}
        assert admit(client, p2["id"], dept["id"], bed["id"]).status_code == 409
        discharge(client, p1["id"])
        msg3 = ws.receive_json()
        assert msg3["patientId"] == p1["id"]  # the discharge, nothing from the 409 in between
    assert client.get("/api/v1/realtime").json()["websocketPath"] == "/api/v1/ws/capacity"


def test_broadcast_failure_does_not_break_the_request(client, realtime_events, caplog):
    dept = create_department(client)
    bed = create_bed(client, dept["id"])
    patient = create_patient(client)

    def boom(_event):
        raise RuntimeError("subscriber exploded")

    event_bus.subscribe(boom)
    try:
        with caplog.at_level(logging.WARNING):
            res = admit(client, patient["id"], dept["id"], bed["id"])
    finally:
        event_bus.unsubscribe(boom)
    assert res.status_code == 200
    assert client.get(f"/api/v1/patients/{patient['id']}").json()["currentStatus"] == "ADMITTED"
    assert any("subscriber failed" in r.message for r in caplog.records)
    assert any(e.type == "PATIENT_UPDATED" for e in realtime_events)


def test_auto_match_emits_match_event_after_release(client, realtime_events):
    dept = create_department(client)
    bed = create_bed(client, dept["id"])
    waiting = create_patient(client)
    client.post("/api/v1/waitlist", json={"patientId": waiting["id"], "departmentId": dept["id"], "resourceType": "BED"})
    client.patch(f"/api/v1/beds/{bed['id']}/status", json={"newStatus": "CLEANING"})
    realtime_events.clear()
    release_bed(client, bed["id"])
    types = [e.type for e in realtime_events]
    # release event first (committed before matching starts), then the assignment events
    assert types[0] == "BED_UPDATED" and realtime_events[0].new_state == "AVAILABLE"
    assert "MATCH_ASSIGNED" in types and "PATIENT_UPDATED" in types and "WAITLIST_UPDATED" in types
    assert types.index("PATIENT_UPDATED") > 0
