"""Audit trail, patient history ordering, actor tracking and history survival
after deactivation."""
from tests.helpers import (
    ACTOR,
    admit,
    create_bed,
    create_department,
    create_patient,
    create_staff,
    create_surgery,
    create_theatre,
    create_slot_ok,
    discharge,
    event_types,
    events,
    release_bed,
    transfer,
)


def test_patient_history_is_chronological_and_complete(client):
    dept_a = create_department(client)
    dept_b = create_department(client)
    bed_a = create_bed(client, dept_a["id"])
    bed_b = create_bed(client, dept_b["id"])
    patient = create_patient(client)

    assert admit(client, patient["id"], dept_a["id"], bed_a["id"], headers=ACTOR).status_code == 200
    assert transfer(client, patient["id"], dept_b["id"], bed_b["id"], headers=ACTOR).status_code == 200
    assert discharge(client, patient["id"], headers=ACTOR).status_code == 200

    res = client.get(f"/api/v1/patients/{patient['id']}/history")
    assert res.status_code == 200
    history = res.json()
    assert [h["eventType"] for h in history] == [
        "RESOURCE_CREATED", "ADMISSION", "TRANSFER", "BED_RELEASE", "DISCHARGE", "BED_RELEASE",
    ]
    timestamps = [h["timestamp"] for h in history]
    assert timestamps == sorted(timestamps)
    assert res.headers["X-Total-Count"] == "6"

    admission = history[1]
    assert admission["previousState"] == "REGISTERED" and admission["newState"] == "ADMITTED"
    assert admission["toBedId"] == bed_a["id"] and admission["toDepartmentId"] == dept_a["id"]
    assert admission["actorId"] == "nurse-7" and admission["actorName"] == "Nurse Seven"
    assert admission["source"] == "MANUAL"
    assert history[0]["actorId"] == "system"  # created without headers

    transfer_evt = history[2]
    assert transfer_evt["fromBedId"] == bed_a["id"] and transfer_evt["toBedId"] == bed_b["id"]
    assert transfer_evt["previousState"] == "ADMITTED" and transfer_evt["newState"] == "TRANSFERRED"
    bed_release = history[3]
    assert bed_release["resourceType"] == "BED" and bed_release["resourceId"] == bed_a["id"]
    assert bed_release["previousState"] == "OCCUPIED" and bed_release["newState"] == "CLEANING"


def test_history_404_for_unknown_patient(client):
    res = client.get("/api/v1/patients/9999/history")
    assert res.status_code == 404
    assert res.json()["error"] == "NOT_FOUND"


def test_actor_defaults_and_headers(client):
    dept = create_department(client)
    bed = create_bed(client, dept["id"])
    patient = create_patient(client)
    admit(client, patient["id"], dept["id"], bed["id"], headers={"X-Actor-ID": "dr-house"})
    evt = events(client, patientId=patient["id"], eventType="ADMISSION")[0]
    assert evt["actorId"] == "dr-house"
    assert evt["actorName"] == "dr-house"  # name falls back to the id
    discharge(client, patient["id"])
    evt = events(client, patientId=patient["id"], eventType="DISCHARGE")[0]
    assert evt["actorId"] == "system" and evt["actorName"] == "System"


def test_every_mutation_creates_an_event_with_states(client):
    dept = create_department(client)
    bed = create_bed(client, dept["id"])
    patient = create_patient(client)
    theatre = create_theatre(client, dept["id"])
    slot = create_slot_ok(client, theatre["id"])
    staff = create_staff(client, dept["id"], role="SURGEON")
    surgery = create_surgery(client, patient["id"], dept["id"], required_role="SURGEON")

    def evt(resource_type, resource_id, event_type):
        found = events(client, resourceType=resource_type, resourceId=resource_id, eventType=event_type)
        assert found, (resource_type, resource_id, event_type)
        return found[0]

    assert evt("DEPARTMENT", dept["id"], "RESOURCE_CREATED")["newState"] == "ACTIVE"
    assert evt("BED", bed["id"], "RESOURCE_CREATED")["newState"] == "AVAILABLE"
    assert evt("PATIENT", patient["id"], "RESOURCE_CREATED")["newState"] == "REGISTERED"
    assert evt("THEATRE", theatre["id"], "RESOURCE_CREATED")["newState"] == "AVAILABLE"
    assert evt("THEATRE_SLOT", slot["id"], "THEATRE_SLOT_CREATED")["newState"] == "AVAILABLE"
    assert evt("STAFF", staff["id"], "RESOURCE_CREATED")["newState"] == "AVAILABLE"
    assert evt("SURGERY", surgery["id"], "SURGERY_CREATED")["newState"] == "WAITING"

    # bed status change
    client.patch(f"/api/v1/beds/{bed['id']}/status", json={"newStatus": "MAINTENANCE"}, headers=ACTOR)
    e = evt("BED", bed["id"], "BED_STATUS_CHANGE")
    assert e["previousState"] == "AVAILABLE" and e["newState"] == "MAINTENANCE" and e["actorId"] == "nurse-7"

    # schedule -> slot booked
    assert client.post(f"/api/v1/surgeries/{surgery['id']}/schedule", json={"slotId": slot["id"]}, headers=ACTOR).status_code == 200
    e = evt("SURGERY", surgery["id"], "SURGERY_SCHEDULED")
    assert e["previousState"] == "WAITING" and e["newState"] == "SCHEDULED"
    e = evt("THEATRE_SLOT", slot["id"], "THEATRE_SLOT_BOOKED")
    assert e["previousState"] == "AVAILABLE" and e["newState"] == "BOOKED"
    assert evt("WAITLIST_ENTRY", None, "WAITLIST_FULFILLED")["patientId"] == patient["id"]

    # staff assigned
    res = client.post(f"/api/v1/staff/{staff['id']}/assign", json={"assignmentType": "SURGERY", "surgeryId": surgery["id"]}, headers=ACTOR)
    assert res.status_code == 201, res.text
    e = evt("STAFF", staff["id"], "STAFF_ASSIGNED")
    assert e["previousState"] == "AVAILABLE" and e["newState"] == "ASSIGNED"

    # start + complete
    assert client.post(f"/api/v1/surgeries/{surgery['id']}/start", json={}, headers=ACTOR).status_code == 200
    e = evt("THEATRE", theatre["id"], "THEATRE_STATUS_CHANGE")
    assert e["previousState"] == "AVAILABLE" and e["newState"] == "IN_USE"
    assert client.post(f"/api/v1/surgeries/{surgery['id']}/complete", json={}, headers=ACTOR).status_code == 200
    assert evt("SURGERY", surgery["id"], "SURGERY_COMPLETED")["newState"] == "COMPLETED"
    e = evt("STAFF", staff["id"], "STAFF_RELEASED")
    assert e["previousState"] == "ASSIGNED" and e["newState"] == "AVAILABLE"
    assert evt("THEATRE_SLOT", slot["id"], "THEATRE_SLOT_COMPLETED")["newState"] == "COMPLETED"
    theatre_events = event_types(client, resourceType="THEATRE", resourceId=theatre["id"])
    assert theatre_events[0] == "THEATRE_STATUS_CHANGE"
    assert events(client, resourceType="THEATRE", resourceId=theatre["id"])[0]["newState"] == "CLEANING"


def test_deactivating_department_and_bed_keeps_history(client):
    dept = create_department(client)
    bed = create_bed(client, dept["id"])
    patient = create_patient(client)
    admit(client, patient["id"], dept["id"], bed["id"], headers=ACTOR)
    discharge(client, patient["id"], headers=ACTOR)
    history_before = client.get(f"/api/v1/patients/{patient['id']}/history").json()
    assert len(history_before) == 4

    # bed still CLEANING -> release so it can be deactivated
    release_bed(client, bed["id"], auto_assign=False)
    assert client.delete(f"/api/v1/beds/{bed['id']}", headers=ACTOR).status_code == 200
    assert client.delete(f"/api/v1/departments/{dept['id']}", headers=ACTOR).status_code == 200

    history_after = client.get(f"/api/v1/patients/{patient['id']}/history").json()
    assert [h["id"] for h in history_before] == [h["id"] for h in history_after[: len(history_before)]]
    # the bed / department events themselves are still queryable
    assert "RESOURCE_DEACTIVATED" in event_types(client, resourceType="BED", resourceId=bed["id"])
    assert "RESOURCE_DEACTIVATED" in event_types(client, resourceType="DEPARTMENT", resourceId=dept["id"])
    assert client.get(f"/api/v1/beds/{bed['id']}").json()["isActive"] is False
    assert client.get(f"/api/v1/departments/{dept['id']}").json()["isActive"] is False
    assert client.get("/api/v1/departments").json() == []
    assert len(client.get("/api/v1/departments?includeInactive=true").json()) == 1


def test_department_with_occupied_bed_cannot_be_deactivated(client):
    dept = create_department(client)
    bed = create_bed(client, dept["id"])
    patient = create_patient(client)
    admit(client, patient["id"], dept["id"], bed["id"])
    assert client.delete(f"/api/v1/departments/{dept['id']}").status_code == 409
    assert client.delete(f"/api/v1/beds/{bed['id']}").status_code == 409
    assert client.get(f"/api/v1/departments/{dept['id']}").json()["isActive"] is True


def test_flow_events_filters_and_pagination(client):
    dept = create_department(client)
    for _ in range(3):
        create_bed(client, dept["id"])
    res = client.get("/api/v1/flow-events", params={"resourceType": "BED", "limit": 2, "offset": 0})
    assert res.status_code == 200
    assert len(res.json()) == 2
    assert res.headers["X-Total-Count"] == "3"
    ids = [e["id"] for e in res.json()]
    assert ids == sorted(ids, reverse=True)  # newest first
    res2 = client.get("/api/v1/flow-events", params={"resourceType": "BED", "limit": 2, "offset": 2})
    assert len(res2.json()) == 1
