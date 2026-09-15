"""Staff: assignment, release, incompatible role/department/shift, overlapping assignment, status rules."""
from tests.helpers import (
    admit,
    create_bed,
    create_department,
    create_patient,
    create_slot_ok,
    create_staff,
    create_surgery,
    create_theatre,
)


def _admitted_patient(client, dept):
    bed = create_bed(client, dept["id"])
    patient = create_patient(client)
    assert admit(client, patient["id"], dept["id"], bed["id"]).status_code == 200
    return patient


def test_create_and_status_rules(client):
    dept = create_department(client)
    staff = create_staff(client, dept["id"], role="NURSE")
    assert staff["status"] == "AVAILABLE"
    assert client.post("/api/v1/staff", json={"name": "X", "role": "NURSE", "departmentId": dept["id"],
                                             "shiftStart": "2026-09-16T08:00:00Z", "shiftEnd": "2026-09-16T07:00:00Z"}).status_code == 422
    assert client.post("/api/v1/staff", json={"name": "X", "role": "NURSE", "departmentId": dept["id"],
                                             "shiftStart": "2026-09-16T08:00:00Z", "shiftEnd": "2026-09-16T17:00:00Z",
                                             "status": "ASSIGNED"}).status_code == 409
    assert client.post("/api/v1/staff", json={"name": "X", "role": "WIZARD", "departmentId": dept["id"],
                                             "shiftStart": "2026-09-16T08:00:00Z", "shiftEnd": "2026-09-16T17:00:00Z"}).status_code == 422
    # ASSIGNED cannot be set manually; OFF_DUTY <-> AVAILABLE can
    assert client.patch(f"/api/v1/staff/{staff['id']}/status", json={"newStatus": "ASSIGNED"}).status_code == 409
    assert client.patch(f"/api/v1/staff/{staff['id']}/status", json={"newStatus": "OFF_DUTY"}).status_code == 200
    assert client.patch(f"/api/v1/staff/{staff['id']}/status", json={"newStatus": "OFF_DUTY"}).status_code == 409
    assert client.patch(f"/api/v1/staff/{staff['id']}/status", json={"newStatus": "AVAILABLE"}).status_code == 200
    assert client.get("/api/v1/staff/9999").status_code == 404


def test_assign_and_release_patient_assignment(client):
    dept = create_department(client)
    nurse = create_staff(client, dept["id"], role="NURSE")
    patient = _admitted_patient(client, dept)
    res = client.post(f"/api/v1/staff/{nurse['id']}/assign", json={"assignmentType": "PATIENT", "patientId": patient["id"]})
    assert res.status_code == 201, res.text
    assignment = res.json()
    assert assignment["patientId"] == patient["id"] and assignment["status"] == "ACTIVE" and assignment["endTime"] is None
    assert client.get(f"/api/v1/staff/{nurse['id']}").json()["status"] == "ASSIGNED"
    # cannot go off duty while assigned, cannot be deactivated
    assert client.patch(f"/api/v1/staff/{nurse['id']}/status", json={"newStatus": "OFF_DUTY"}).status_code == 409
    assert client.delete(f"/api/v1/staff/{nurse['id']}").status_code == 409

    res = client.post(f"/api/v1/staff-assignments/{assignment['id']}/release", json={"autoAssign": False})
    assert res.status_code == 200
    assert res.json()["assignment"]["status"] == "RELEASED" and res.json()["assignment"]["releasedAt"]
    assert client.get(f"/api/v1/staff/{nurse['id']}").json()["status"] == "AVAILABLE"
    assert client.post(f"/api/v1/staff-assignments/{assignment['id']}/release", json={}).status_code == 409
    assert client.get("/api/v1/staff-assignments", params={"staffId": nurse["id"]}).headers["X-Total-Count"] == "1"


def test_overlapping_assignment_is_rejected(client):
    dept = create_department(client)
    nurse = create_staff(client, dept["id"], role="NURSE")
    p1 = _admitted_patient(client, dept)
    p2 = _admitted_patient(client, dept)
    assert client.post(f"/api/v1/staff/{nurse['id']}/assign", json={"assignmentType": "PATIENT", "patientId": p1["id"]}).status_code == 201
    res = client.post(f"/api/v1/staff/{nurse['id']}/assign", json={"assignmentType": "PATIENT", "patientId": p2["id"]})
    assert res.status_code == 409
    assert client.get("/api/v1/staff-assignments", params={"status": "ACTIVE"}).headers["X-Total-Count"] == "1"


def test_incompatible_role_department_and_shift(client):
    dept = create_department(client)
    other = create_department(client)
    theatre = create_theatre(client, dept["id"])
    slot = create_slot_ok(client, theatre["id"], minutes=60)
    patient = create_patient(client)
    surgery = create_surgery(client, patient["id"], dept["id"], duration=60, required_role="SURGEON")
    assert client.post(f"/api/v1/surgeries/{surgery['id']}/schedule", json={"slotId": slot["id"]}).status_code == 200

    nurse = create_staff(client, dept["id"], role="NURSE")
    res = client.post(f"/api/v1/staff/{nurse['id']}/assign", json={"assignmentType": "SURGERY", "surgeryId": surgery["id"]})
    assert res.status_code == 409 and "SURGEON" in res.json()["message"]

    foreign_surgeon = create_staff(client, other["id"], role="SURGEON")
    res = client.post(f"/api/v1/staff/{foreign_surgeon['id']}/assign", json={"assignmentType": "SURGERY", "surgeryId": surgery["id"]})
    assert res.status_code == 409 and "department" in res.json()["message"]

    off_shift_surgeon = create_staff(client, dept["id"], role="SURGEON", shift_hours=(-10, -5))
    res = client.post(f"/api/v1/staff/{off_shift_surgeon['id']}/assign", json={"assignmentType": "SURGERY", "surgeryId": surgery["id"]})
    assert res.status_code == 409 and "shift" in res.json()["message"]

    off_duty = create_staff(client, dept["id"], role="SURGEON", status="OFF_DUTY")
    assert client.post(f"/api/v1/staff/{off_duty['id']}/assign", json={"assignmentType": "SURGERY", "surgeryId": surgery["id"]}).status_code == 409

    surgeon = create_staff(client, dept["id"], role="SURGEON")
    assert client.post(f"/api/v1/staff/{surgeon['id']}/assign", json={"assignmentType": "SURGERY", "surgeryId": surgery["id"]}).status_code == 201
    # validation of payload
    assert client.post(f"/api/v1/staff/{surgeon['id']}/assign", json={"assignmentType": "SURGERY"}).status_code == 422
    assert client.post(f"/api/v1/staff/{nurse['id']}/assign", json={"assignmentType": "PATIENT", "patientId": 9999}).status_code == 404
    assert client.post(f"/api/v1/staff/{nurse['id']}/assign", json={"assignmentType": "PATIENT", "patientId": patient["id"]}).status_code == 409  # not in a department


def test_staff_listing_filters(client):
    dept = create_department(client)
    create_staff(client, dept["id"], role="NURSE")
    create_staff(client, dept["id"], role="SURGEON")
    off = create_staff(client, dept["id"], role="NURSE", status="OFF_DUTY")
    assert client.get("/api/v1/staff", params={"role": "NURSE"}).headers["X-Total-Count"] == "2"
    assert client.get("/api/v1/staff", params={"status": "OFF_DUTY"}).json()[0]["id"] == off["id"]
    assert client.delete(f"/api/v1/staff/{off['id']}").status_code == 200
    assert client.get("/api/v1/staff").headers["X-Total-Count"] == "2"
    assert client.get("/api/v1/staff", params={"includeInactive": "true"}).headers["X-Total-Count"] == "3"
