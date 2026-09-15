"""Surgery lifecycle: creation, scheduling, start, completion, cancellation, invalid scheduling."""
from tests.helpers import (
    create_department,
    create_patient,
    create_slot_ok,
    create_staff,
    create_surgery,
    create_theatre,
    admit,
    create_bed,
    discharge,
)


def test_create_surgery_validation(client):
    dept = create_department(client)
    patient = create_patient(client)
    base = {"patientId": patient["id"], "departmentId": dept["id"], "procedureName": "Op", "durationMinutes": 60, "priority": 3}
    assert client.post("/api/v1/surgeries", json=base | {"durationMinutes": 5}).status_code == 422
    assert client.post("/api/v1/surgeries", json=base | {"priority": 9}).status_code == 422
    assert client.post("/api/v1/surgeries", json=base | {"patientId": 9999}).status_code == 404
    assert client.post("/api/v1/surgeries", json=base | {"departmentId": 9999}).status_code == 404
    res = client.post("/api/v1/surgeries", json=base)
    assert res.status_code == 201
    surgery = res.json()
    assert surgery["status"] == "WAITING" and surgery["slotId"] is None
    # the surgery sits on the THEATRE queue
    queue = client.get("/api/v1/waitlist", params={"resourceType": "THEATRE"}).json()
    assert len(queue) == 1 and queue[0]["surgeryId"] == surgery["id"] and queue[0]["priority"] == 3
    # discharged patient cannot get a surgery
    bed = create_bed(client, dept["id"])
    admit(client, patient["id"], dept["id"], bed["id"])
    discharge(client, patient["id"])
    assert client.post("/api/v1/surgeries", json=base).status_code == 409


def test_full_surgery_lifecycle(client):
    dept = create_department(client)
    theatre = create_theatre(client, dept["id"])
    slot = create_slot_ok(client, theatre["id"], minutes=120)
    patient = create_patient(client)
    surgeon = create_staff(client, dept["id"], role="SURGEON")
    surgery = create_surgery(client, patient["id"], dept["id"], duration=60, required_role="SURGEON")

    # cannot start or complete while WAITING
    assert client.post(f"/api/v1/surgeries/{surgery['id']}/start", json={}).status_code == 409
    assert client.post(f"/api/v1/surgeries/{surgery['id']}/complete", json={}).status_code == 409

    assert client.post(f"/api/v1/surgeries/{surgery['id']}/schedule", json={"slotId": slot["id"]}).status_code == 200
    # requires assigned SURGEON before start
    assert client.post(f"/api/v1/surgeries/{surgery['id']}/start", json={}).status_code == 409
    res = client.post(f"/api/v1/staff/{surgeon['id']}/assign", json={"assignmentType": "SURGERY", "surgeryId": surgery["id"]})
    assert res.status_code == 201, res.text
    assignment = res.json()
    assert assignment["status"] == "ACTIVE" and assignment["surgeryId"] == surgery["id"]

    res = client.post(f"/api/v1/surgeries/{surgery['id']}/start", json={})
    assert res.status_code == 200 and res.json()["status"] == "IN_PROGRESS" and res.json()["startedAt"]
    assert client.get(f"/api/v1/theatres/{theatre['id']}").json()["status"] == "IN_USE"
    # cannot cancel or unschedule once in progress
    assert client.post(f"/api/v1/surgeries/{surgery['id']}/cancel", json={}).status_code == 409
    assert client.post(f"/api/v1/surgeries/{surgery['id']}/unschedule", json={}).status_code == 409

    res = client.post(f"/api/v1/surgeries/{surgery['id']}/complete", json={})
    assert res.status_code == 200
    assert res.json()["surgery"]["status"] == "COMPLETED" and res.json()["surgery"]["completedAt"]
    assert client.get(f"/api/v1/theatres/{theatre['id']}").json()["status"] == "CLEANING"
    assert client.get(f"/api/v1/theatre-slots/{slot['id']}").json()["status"] == "COMPLETED"
    assert client.get(f"/api/v1/staff/{surgeon['id']}").json()["status"] == "AVAILABLE"
    assert client.get(f"/api/v1/staff-assignments/{assignment['id']}").json()["status"] == "RELEASED"
    # terminal
    assert client.post(f"/api/v1/surgeries/{surgery['id']}/cancel", json={}).status_code == 409
    assert client.post(f"/api/v1/surgeries/{surgery['id']}/complete", json={}).status_code == 409


def test_cancel_waiting_and_scheduled_surgery(client):
    dept = create_department(client)
    theatre = create_theatre(client, dept["id"])
    slot = create_slot_ok(client, theatre["id"], minutes=120)
    p1, p2 = create_patient(client), create_patient(client)
    waiting = create_surgery(client, p1["id"], dept["id"])
    scheduled = create_surgery(client, p2["id"], dept["id"])
    nurse = create_staff(client, dept["id"], role="NURSE")
    assert client.post(f"/api/v1/surgeries/{scheduled['id']}/schedule", json={"slotId": slot["id"]}).status_code == 200
    assert client.post(f"/api/v1/staff/{nurse['id']}/assign", json={"assignmentType": "SURGERY", "surgeryId": scheduled["id"]}).status_code == 201

    res = client.post(f"/api/v1/surgeries/{waiting['id']}/cancel", json={"autoAssign": False})
    assert res.status_code == 200 and res.json()["surgery"]["status"] == "CANCELLED"
    queue = client.get("/api/v1/waitlist", params={"resourceType": "THEATRE"}).json()
    assert queue == []  # p1 cancelled, p2 fulfilled

    res = client.post(f"/api/v1/surgeries/{scheduled['id']}/cancel", json={"autoAssign": False})
    assert res.status_code == 200 and res.json()["surgery"]["status"] == "CANCELLED"
    assert client.get(f"/api/v1/theatre-slots/{slot['id']}").json()["status"] == "AVAILABLE"
    assert client.get(f"/api/v1/staff/{nurse['id']}").json()["status"] == "AVAILABLE"
    assert client.get("/api/v1/waitlist", params={"status": "CANCELLED"}).headers["X-Total-Count"] == "1"


def test_surgery_listing_order_and_filters(client):
    dept = create_department(client)
    patients = [create_patient(client) for _ in range(3)]
    s_low = create_surgery(client, patients[0]["id"], dept["id"], priority=5)
    s_high = create_surgery(client, patients[1]["id"], dept["id"], priority=1)
    s_mid = create_surgery(client, patients[2]["id"], dept["id"], priority=3)
    res = client.get("/api/v1/surgeries", params={"status": "WAITING"})
    assert [s["id"] for s in res.json()] == [s_high["id"], s_mid["id"], s_low["id"]]
    assert res.headers["X-Total-Count"] == "3"
    assert client.get("/api/v1/surgeries", params={"patientId": patients[0]["id"]}).json()[0]["id"] == s_low["id"]
    assert client.get("/api/v1/surgeries/9999").status_code == 404
