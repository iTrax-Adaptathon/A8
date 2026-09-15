"""Waitlist: add/remove, deterministic ordering (priority, then longest wait, then id)."""
from datetime import timedelta

from app.infrastructure.database.models import WaitlistEntryModel
from tests.helpers import add_waitlist, admit, create_bed, create_department, create_patient, discharge, now_utc


def test_add_and_remove(client):
    dept = create_department(client)
    patient = create_patient(client)
    res = add_waitlist(client, patient["id"], dept["id"], priority=2, reason="Needs ICU bed", requiredBedType="ICU")
    assert res.status_code == 201, res.text
    entry = res.json()
    assert entry["status"] == "WAITING" and entry["requiredBedType"] == "ICU" and entry["requestedAt"]
    # duplicate waiting request for same resource type
    assert add_waitlist(client, patient["id"], dept["id"]).status_code == 409
    assert client.get(f"/api/v1/waitlist/{entry['id']}").status_code == 200
    assert client.get("/api/v1/waitlist/9999").status_code == 404

    res = client.delete(f"/api/v1/waitlist/{entry['id']}")
    assert res.status_code == 200 and res.json()["status"] == "CANCELLED"
    assert client.delete(f"/api/v1/waitlist/{entry['id']}").status_code == 409
    assert client.get("/api/v1/waitlist").json() == []  # default filter WAITING
    assert client.get("/api/v1/waitlist", params={"status": "CANCELLED"}).headers["X-Total-Count"] == "1"


def test_validation(client):
    dept = create_department(client)
    patient = create_patient(client)
    assert add_waitlist(client, 9999, dept["id"]).status_code == 404
    assert add_waitlist(client, patient["id"], 9999).status_code == 404
    assert add_waitlist(client, patient["id"], dept["id"], priority=0).status_code == 422
    assert add_waitlist(client, patient["id"], dept["id"], resource_type="THEATRE").status_code == 422
    assert add_waitlist(client, patient["id"], dept["id"], resource_type="STAFF").status_code == 422  # role required
    assert add_waitlist(client, patient["id"], dept["id"], resource_type="STAFF", requiredStaffRole="NURSE").status_code == 201
    bed = create_bed(client, dept["id"])
    admit(client, patient["id"], dept["id"], bed["id"])
    discharge(client, patient["id"])
    assert add_waitlist(client, patient["id"], dept["id"]).status_code == 409  # discharged


def test_priority_then_longest_wait_then_id(client, db_session):
    dept = create_department(client)
    patients = [create_patient(client) for _ in range(5)]
    ids = []
    for p, prio in zip(patients, [3, 1, 3, 2, 1]):
        ids.append(add_waitlist(client, p["id"], dept["id"], priority=prio).json()["id"])
    # Make the LAST priority-1 entry the longest waiting and give two priority-3 entries the same timestamp.
    base = now_utc()
    stamps = {ids[0]: base, ids[1]: base + timedelta(minutes=5), ids[2]: base, ids[3]: base + timedelta(minutes=1), ids[4]: base - timedelta(hours=1)}
    for entry_id, ts in stamps.items():
        db_session.get(WaitlistEntryModel, entry_id).requested_at = ts
    db_session.commit()

    order = [e["id"] for e in client.get("/api/v1/waitlist", params={"resourceType": "BED"}).json()]
    # priority 1: ids[4] (waited longest) before ids[1]; priority 2: ids[3]; priority 3 tie on time -> lower id first
    assert order == [ids[4], ids[1], ids[3], ids[0], ids[2]]
    # deterministic: identical result on repeated calls
    assert order == [e["id"] for e in client.get("/api/v1/waitlist", params={"resourceType": "BED"}).json()]
    # pagination keeps the order
    page = client.get("/api/v1/waitlist", params={"resourceType": "BED", "limit": 2, "offset": 1})
    assert [e["id"] for e in page.json()] == [ids[1], ids[3]] and page.headers["X-Total-Count"] == "5"


def test_admission_fulfils_matching_bed_entry_and_discharge_cancels(client):
    dept = create_department(client)
    other = create_department(client)
    bed = create_bed(client, dept["id"])
    patient = create_patient(client)
    entry = add_waitlist(client, patient["id"], dept["id"]).json()
    admit(client, patient["id"], dept["id"], bed["id"])
    assert client.get(f"/api/v1/waitlist/{entry['id']}").json()["status"] == "FULFILLED"
    assert client.get(f"/api/v1/waitlist/{entry['id']}").json()["fulfilledResourceId"] == bed["id"]
    # waiting for a bed in another department (transfer request) stays open until discharge
    entry2 = add_waitlist(client, patient["id"], other["id"]).json()
    discharge(client, patient["id"])
    assert client.get(f"/api/v1/waitlist/{entry2['id']}").json()["status"] == "CANCELLED"
