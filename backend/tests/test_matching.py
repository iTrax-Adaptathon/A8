"""Deterministic matching: eligible / incompatible / multiple candidates,
determinism, read-only GET /matches, confirm, auto-match after release,
rejected auto-assignment never undoes a release."""
from datetime import timedelta

from app.infrastructure.database.models import FlowEventModel, WaitlistEntryModel
from tests.helpers import (
    ACTOR,
    add_waitlist,
    admit,
    create_bed,
    create_department,
    create_patient,
    create_slot_ok,
    create_staff,
    create_surgery,
    create_theatre,
    discharge,
    event_types,
    events,
    now_utc,
    release_bed,
)


def _matches(client, resource_type, resource_id):
    res = client.get("/api/v1/matches", params={"resourceType": resource_type, "resourceId": resource_id})
    assert res.status_code == 200, res.text
    return res.json()


def test_bed_candidates_eligible_incompatible_and_ordered(client, db_session):
    cardio = create_department(client, name="Cardiology", code="CARD")
    other = create_department(client)
    bed = create_bed(client, cardio["id"], bed_type="GENERAL")

    eligible_low = create_patient(client)
    eligible_high = create_patient(client)
    eligible_high_older = create_patient(client)
    wrong_dept = create_patient(client)
    wants_icu = create_patient(client)
    discharged = create_patient(client)

    e1 = add_waitlist(client, eligible_low["id"], cardio["id"], priority=3).json()
    e2 = add_waitlist(client, eligible_high["id"], cardio["id"], priority=1).json()
    e3 = add_waitlist(client, eligible_high_older["id"], cardio["id"], priority=1).json()
    add_waitlist(client, wrong_dept["id"], other["id"], priority=1)
    add_waitlist(client, wants_icu["id"], cardio["id"], priority=1, requiredBedType="ICU")
    # discharged patient with a stale entry (bypass API to build the edge case)
    tmp_bed = create_bed(client, other["id"])
    admit(client, discharged["id"], other["id"], tmp_bed["id"])
    discharge(client, discharged["id"])
    db_session.add(WaitlistEntryModel(patient_id=discharged["id"], resource_type="BED", department_id=cardio["id"], priority=1, requested_at=now_utc() - timedelta(days=1)))
    # make e3 the longest waiting among priority 1
    db_session.get(WaitlistEntryModel, e3["id"]).requested_at = now_utc() - timedelta(hours=3)
    db_session.commit()

    events_before = db_session.query(FlowEventModel).count()
    result = _matches(client, "BED", bed["id"])
    assert result["resourceAvailable"] is True and result["departmentId"] == cardio["id"]
    ranked = [(c["rank"], c["waitlistEntryId"]) for c in result["candidates"]]
    assert ranked == [(1, e3["id"]), (2, e2["id"]), (3, e1["id"])]
    assert result["candidates"][0]["reason"] == "Compatible Cardiology GENERAL bed; priority 1; longest waiting eligible patient."
    assert result["candidates"][2]["reason"].endswith("priority 3; rank 3 in queue.")

    # GET /matches is read-only: no events, no waitlist changes
    assert db_session.query(FlowEventModel).count() == events_before
    assert client.get("/api/v1/waitlist", params={"resourceType": "BED"}).headers["X-Total-Count"] == "6"
    # deterministic
    assert _matches(client, "BED", bed["id"]) == result


def test_matching_ignores_resource_that_is_not_available(client):
    dept = create_department(client)
    bed = create_bed(client, dept["id"])
    patient = create_patient(client)
    add_waitlist(client, patient["id"], dept["id"])
    client.patch(f"/api/v1/beds/{bed['id']}/status", json={"newStatus": "CLEANING"})
    result = _matches(client, "BED", bed["id"])
    assert result["resourceAvailable"] is False and result["candidates"] == []
    assert client.get("/api/v1/matches", params={"resourceType": "BED", "resourceId": 9999}).status_code == 404
    assert client.get("/api/v1/matches", params={"resourceType": "DEPARTMENT", "resourceId": dept["id"]}).status_code == 422


def test_confirm_match_uses_admission_workflow(client):
    dept = create_department(client)
    bed = create_bed(client, dept["id"])
    patient = create_patient(client)
    entry = add_waitlist(client, patient["id"], dept["id"], priority=2).json()
    res = client.post("/api/v1/matches/confirm", json={"resourceType": "BED", "resourceId": bed["id"], "waitlistEntryId": entry["id"]}, headers=ACTOR)
    assert res.status_code == 200, res.text
    body = res.json()
    assert body["matched"] is True and body["patientId"] == patient["id"] and body["waitlistEntryId"] == entry["id"]
    p = client.get(f"/api/v1/patients/{patient['id']}").json()
    assert p["currentStatus"] == "ADMITTED" and p["currentBedId"] == bed["id"]
    assert client.get(f"/api/v1/waitlist/{entry['id']}").json()["status"] == "FULFILLED"
    types = event_types(client, patientId=patient["id"])
    assert "MATCH_IDENTIFIED" in types and "ADMISSION" in types and "WAITLIST_FULFILLED" in types
    match_evt = events(client, patientId=patient["id"], eventType="MATCH_IDENTIFIED")[0]
    assert match_evt["actorId"] == "nurse-7" and match_evt["source"] == "MANUAL" and match_evt["metadata"]["rank"] == 1

    # confirming again -> the entry is no longer waiting
    assert client.post("/api/v1/matches/confirm", json={"resourceType": "BED", "resourceId": bed["id"], "waitlistEntryId": entry["id"]}).status_code == 409


def test_confirm_ineligible_records_rejection(client):
    dept = create_department(client)
    other = create_department(client)
    bed = create_bed(client, dept["id"])
    patient = create_patient(client)
    entry = add_waitlist(client, patient["id"], other["id"]).json()
    res = client.post("/api/v1/matches/confirm", json={"resourceType": "BED", "resourceId": bed["id"], "waitlistEntryId": entry["id"]})
    assert res.status_code == 409 and "department mismatch" in res.json()["message"]
    rejected = events(client, eventType="ASSIGNMENT_REJECTED")
    assert len(rejected) == 1 and rejected[0]["resourceId"] == bed["id"] and rejected[0]["patientId"] == patient["id"]
    assert "MATCH_IDENTIFIED" not in event_types(client)
    assert client.get(f"/api/v1/beds/{bed['id']}").json()["status"] == "AVAILABLE"


def test_auto_match_after_bed_release(client):
    dept = create_department(client)
    bed = create_bed(client, dept["id"])
    occupant = create_patient(client)
    waiting_low = create_patient(client)
    waiting_high = create_patient(client)
    admit(client, occupant["id"], dept["id"], bed["id"])
    low = add_waitlist(client, waiting_low["id"], dept["id"], priority=4).json()
    high = add_waitlist(client, waiting_high["id"], dept["id"], priority=1).json()

    discharge(client, occupant["id"], headers=ACTOR)
    assert client.get(f"/api/v1/beds/{bed['id']}").json()["status"] == "CLEANING"
    # nothing was matched on discharge (bed not AVAILABLE yet)
    assert client.get(f"/api/v1/patients/{waiting_high['id']}").json()["currentStatus"] == "REGISTERED"

    res = release_bed(client, bed["id"], headers=ACTOR)  # default: auto-assign on
    assert res.status_code == 200, res.text
    auto = res.json()["autoAssignment"]
    assert auto["matched"] is True and auto["patientId"] == waiting_high["id"] and auto["waitlistEntryId"] == high["id"]
    assert res.json()["bed"]["status"] == "OCCUPIED" and res.json()["bed"]["currentPatientId"] == waiting_high["id"]
    assert client.get(f"/api/v1/patients/{waiting_high['id']}").json()["currentStatus"] == "ADMITTED"
    assert client.get(f"/api/v1/waitlist/{high['id']}").json()["status"] == "FULFILLED"
    assert client.get(f"/api/v1/waitlist/{low['id']}").json()["status"] == "WAITING"

    evts = events(client, patientId=waiting_high["id"])
    admission = next(e for e in evts if e["eventType"] == "ADMISSION")
    assert admission["source"] == "AUTO_MATCH" and admission["actorId"] == "nurse-7"
    match = next(e for e in evts if e["eventType"] == "MATCH_IDENTIFIED")
    assert match["source"] == "AUTO_MATCH"
    release_evt = events(client, resourceType="BED", resourceId=bed["id"], eventType="BED_STATUS_CHANGE")[0]
    assert release_evt["previousState"] == "CLEANING" and release_evt["newState"] == "AVAILABLE"


def test_release_without_auto_assign_and_manual_assign_later(client):
    dept = create_department(client)
    bed = create_bed(client, dept["id"])
    patient = create_patient(client)
    add_waitlist(client, patient["id"], dept["id"])
    client.patch(f"/api/v1/beds/{bed['id']}/status", json={"newStatus": "CLEANING"})
    res = release_bed(client, bed["id"], auto_assign=False)
    assert res.json()["autoAssignment"] is None and res.json()["bed"]["status"] == "AVAILABLE"
    assert _matches(client, "BED", bed["id"])["candidates"][0]["patientId"] == patient["id"]


def test_auto_match_with_no_candidates_keeps_bed_available(client):
    dept = create_department(client)
    bed = create_bed(client, dept["id"])
    client.patch(f"/api/v1/beds/{bed['id']}/status", json={"newStatus": "CLEANING"})
    res = release_bed(client, bed["id"])
    assert res.json()["bed"]["status"] == "AVAILABLE"
    assert res.json()["autoAssignment"]["matched"] is False and res.json()["autoAssignment"]["candidatesEvaluated"] == 0


def test_rejected_auto_assignment_does_not_undo_release(client, db_session):
    """A candidate that passes the eligibility filter but is refused by the
    validated workflow leaves the release committed and records a rejection."""
    from app.infrastructure.database.models import DepartmentModel

    dept = create_department(client)
    bed = create_bed(client, dept["id"])
    patient = create_patient(client)
    entry = add_waitlist(client, patient["id"], dept["id"]).json()
    client.patch(f"/api/v1/beds/{bed['id']}/status", json={"newStatus": "CLEANING"})
    # The admission workflow refuses inactive departments; the matching filter does not look at it.
    db_session.get(DepartmentModel, dept["id"]).is_active = False
    db_session.commit()

    res = release_bed(client, bed["id"])
    assert res.status_code == 200, res.text
    assert res.json()["bed"]["status"] == "AVAILABLE"  # release stayed committed
    auto = res.json()["autoAssignment"]
    assert auto["matched"] is False and auto["candidatesEvaluated"] == 1
    assert auto["rejections"][0]["waitlistEntryId"] == entry["id"]
    rejected = events(client, eventType="ASSIGNMENT_REJECTED")
    assert rejected and rejected[0]["resourceId"] == bed["id"] and rejected[0]["source"] == "AUTO_MATCH"
    assert "MATCH_IDENTIFIED" not in event_types(client, patientId=patient["id"])
    assert client.get(f"/api/v1/waitlist/{entry['id']}").json()["status"] == "WAITING"
    assert client.get(f"/api/v1/patients/{patient['id']}").json()["currentStatus"] == "REGISTERED"


def test_theatre_slot_matching_and_auto_match_on_slot_release(client):
    dept = create_department(client, name="Surgical", code="SURG")
    theatre = create_theatre(client, dept["id"])
    slot = create_slot_ok(client, theatre["id"], minutes=90)
    p_long, p_urgent, p_routine = create_patient(client), create_patient(client), create_patient(client)
    too_long = create_surgery(client, p_long["id"], dept["id"], duration=120, priority=1)
    urgent = create_surgery(client, p_urgent["id"], dept["id"], duration=60, priority=2)
    routine = create_surgery(client, p_routine["id"], dept["id"], duration=60, priority=4)

    result = _matches(client, "THEATRE_SLOT", slot["id"])
    assert [c["surgeryId"] for c in result["candidates"]] == [urgent["id"], routine["id"]]
    assert "90 min >= 60 min" in result["candidates"][0]["reason"]

    # schedule urgent manually, then cancel -> slot released -> routine auto-matched
    assert client.post(f"/api/v1/surgeries/{urgent['id']}/schedule", json={"slotId": slot["id"]}).status_code == 200
    res = client.post(f"/api/v1/surgeries/{urgent['id']}/cancel", json={})
    assert res.status_code == 200
    auto = res.json()["autoAssignments"]
    assert len(auto) == 1 and auto[0]["matched"] is True and auto[0]["surgeryId"] == routine["id"]
    assert client.get(f"/api/v1/surgeries/{routine['id']}").json()["status"] == "SCHEDULED"
    assert client.get(f"/api/v1/theatre-slots/{slot['id']}").json()["surgeryId"] == routine["id"]
    assert client.get(f"/api/v1/surgeries/{too_long['id']}").json()["status"] == "WAITING"

    # theatre release only re-evaluates slots that are genuinely AVAILABLE
    free_slot = create_slot_ok(client, theatre["id"], start=now_utc() + timedelta(hours=6), minutes=180, auto_assign=False)
    client.patch(f"/api/v1/theatres/{theatre['id']}/status", json={"newStatus": "CLEANING"})
    res = client.post(f"/api/v1/theatres/{theatre['id']}/release", json={})
    assert res.status_code == 200
    auto = res.json()["autoAssignments"]
    assert [a["resourceId"] for a in auto] == [free_slot["id"]]
    assert auto[0]["matched"] is True and auto[0]["surgeryId"] == too_long["id"]


def test_staff_matching_and_auto_match_on_release(client):
    dept = create_department(client)
    nurse = create_staff(client, dept["id"], role="NURSE")
    bed_a, bed_b = create_bed(client, dept["id"]), create_bed(client, dept["id"])
    p_a, p_b = create_patient(client), create_patient(client)
    admit(client, p_a["id"], dept["id"], bed_a["id"])
    admit(client, p_b["id"], dept["id"], bed_b["id"])
    assert client.post(f"/api/v1/staff/{nurse['id']}/assign", json={"assignmentType": "PATIENT", "patientId": p_a["id"]}).status_code == 201
    assignment_id = client.get("/api/v1/staff-assignments", params={"status": "ACTIVE"}).json()[0]["id"]

    needs_nurse = add_waitlist(client, p_b["id"], dept["id"], resource_type="STAFF", requiredStaffRole="NURSE", priority=2).json()
    p_c = create_patient(client)
    add_waitlist(client, p_c["id"], dept["id"], resource_type="STAFF", requiredStaffRole="SURGEON", priority=1)

    assert _matches(client, "STAFF", nurse["id"])["resourceAvailable"] is False
    res = client.post(f"/api/v1/staff-assignments/{assignment_id}/release", json={})
    assert res.status_code == 200
    auto = res.json()["autoAssignment"]
    assert auto["matched"] is True and auto["patientId"] == p_b["id"] and auto["waitlistEntryId"] == needs_nurse["id"]
    assert client.get(f"/api/v1/staff/{nurse['id']}").json()["status"] == "ASSIGNED"
    assert client.get(f"/api/v1/waitlist/{needs_nurse['id']}").json()["status"] == "FULFILLED"
    assert client.get("/api/v1/waitlist", params={"resourceType": "STAFF"}).headers["X-Total-Count"] == "1"  # surgeon request remains
