"""Theatres and theatre slots: availability, booking, duplicate booking,
overlap, invalid duration, release; theatre status independent from slots."""
from datetime import timedelta

from tests.helpers import (
    create_department,
    create_patient,
    create_slot,
    create_slot_ok,
    create_surgery,
    create_theatre,
    iso,
    now_utc,
)


def test_theatre_crud_and_status_transitions(client):
    dept = create_department(client)
    theatre = create_theatre(client, dept["id"])
    assert theatre["status"] == "AVAILABLE" and theatre["isActive"] is True
    assert client.get(f"/api/v1/theatres/{theatre['id']}").status_code == 200
    assert client.get("/api/v1/theatres/9999").status_code == 404

    # IN_USE cannot be set manually
    assert client.patch(f"/api/v1/theatres/{theatre['id']}/status", json={"newStatus": "IN_USE"}).status_code == 409
    assert client.patch(f"/api/v1/theatres/{theatre['id']}/status", json={"newStatus": "UNAVAILABLE"}).status_code == 200
    # release only from CLEANING
    assert client.post(f"/api/v1/theatres/{theatre['id']}/release", json={"autoAssign": False}).status_code == 409
    assert client.patch(f"/api/v1/theatres/{theatre['id']}/status", json={"newStatus": "AVAILABLE"}).status_code == 200
    assert client.patch(f"/api/v1/theatres/{theatre['id']}/status", json={"newStatus": "CLEANING"}).status_code == 200
    res = client.post(f"/api/v1/theatres/{theatre['id']}/release", json={"autoAssign": False})
    assert res.status_code == 200 and res.json()["theatre"]["status"] == "AVAILABLE"
    assert res.json()["autoAssignments"] == []

    # creating a theatre IN_USE is rejected
    assert client.post("/api/v1/theatres", json={"name": "Bad", "departmentId": dept["id"], "status": "IN_USE"}).status_code == 409
    assert client.post("/api/v1/theatres", json={"name": "NoDept", "departmentId": 9999}).status_code == 404


def test_slot_validation_window_and_overlap(client):
    dept = create_department(client)
    theatre = create_theatre(client, dept["id"])
    start = now_utc() + timedelta(hours=1)

    # invalid duration: end before start / too short / too long
    assert client.post("/api/v1/theatre-slots", json={"theatreId": theatre["id"], "startTime": iso(start), "endTime": iso(start - timedelta(minutes=30))}).status_code == 422
    assert create_slot(client, theatre["id"], start, minutes=10).status_code == 422
    assert create_slot(client, theatre["id"], start, minutes=25 * 60).status_code == 422

    ok = create_slot_ok(client, theatre["id"], start, minutes=120)
    assert ok["status"] == "AVAILABLE" and ok["durationMinutes"] == 120

    # overlapping slots are rejected (409); adjacent slots are fine
    assert create_slot(client, theatre["id"], start + timedelta(minutes=60), minutes=60).status_code == 409
    assert create_slot(client, theatre["id"], start - timedelta(minutes=30), minutes=60).status_code == 409
    assert create_slot(client, theatre["id"], start + timedelta(minutes=120), minutes=60).status_code == 201
    # a cancelled slot no longer blocks
    later = create_slot_ok(client, theatre["id"], start + timedelta(hours=5), minutes=60)
    assert client.post(f"/api/v1/theatre-slots/{later['id']}/cancel", json={}).status_code == 200
    assert create_slot(client, theatre["id"], start + timedelta(hours=5), minutes=60).status_code == 201
    # unknown theatre
    assert create_slot(client, 9999, start + timedelta(hours=9)).status_code == 404
    # timezone offsets are normalised to UTC
    res = client.post("/api/v1/theatre-slots", json={"theatreId": theatre["id"], "startTime": (start + timedelta(hours=12)).isoformat() + "+02:00",
                                                     "endTime": (start + timedelta(hours=13)).isoformat() + "+02:00"})
    assert res.status_code == 201
    assert res.json()["slot"]["startTime"].endswith("Z")


def test_slot_listing_filters_and_order(client):
    dept = create_department(client)
    theatre = create_theatre(client, dept["id"])
    base = now_utc() + timedelta(hours=1)
    s2 = create_slot_ok(client, theatre["id"], base + timedelta(hours=4), 60)
    s1 = create_slot_ok(client, theatre["id"], base, 60)
    res = client.get("/api/v1/theatre-slots", params={"theatreId": theatre["id"]})
    assert [s["id"] for s in res.json()] == [s1["id"], s2["id"]]
    assert res.headers["X-Total-Count"] == "2"
    res = client.get("/api/v1/theatre-slots", params={"theatreId": theatre["id"], "startFrom": iso(base + timedelta(hours=2))})
    assert [s["id"] for s in res.json()] == [s2["id"]]


def test_booking_duplicate_booking_and_release(client):
    dept = create_department(client)
    theatre = create_theatre(client, dept["id"])
    slot = create_slot_ok(client, theatre["id"], minutes=120)
    p1, p2 = create_patient(client), create_patient(client)
    s1 = create_surgery(client, p1["id"], dept["id"], duration=60)
    s2 = create_surgery(client, p2["id"], dept["id"], duration=60)

    res = client.post(f"/api/v1/surgeries/{s1['id']}/schedule", json={"slotId": slot["id"]})
    assert res.status_code == 200, res.text
    assert res.json()["status"] == "SCHEDULED" and res.json()["slotId"] == slot["id"] and res.json()["theatreId"] == theatre["id"]
    slot_after = client.get(f"/api/v1/theatre-slots/{slot['id']}").json()
    assert slot_after["status"] == "BOOKED" and slot_after["surgeryId"] == s1["id"]

    # duplicate booking of the same slot
    assert client.post(f"/api/v1/surgeries/{s2['id']}/schedule", json={"slotId": slot["id"]}).status_code == 409
    # a booked slot cannot be cancelled
    assert client.post(f"/api/v1/theatre-slots/{slot['id']}/cancel", json={}).status_code == 409
    # theatre with booked slot cannot be deactivated
    assert client.delete(f"/api/v1/theatres/{theatre['id']}").status_code == 409

    # release via unschedule: slot AVAILABLE, surgery WAITING again
    res = client.post(f"/api/v1/surgeries/{s1['id']}/unschedule", json={"autoAssign": False})
    assert res.status_code == 200
    assert res.json()["surgery"]["status"] == "WAITING" and res.json()["surgery"]["slotId"] is None
    assert client.get(f"/api/v1/theatre-slots/{slot['id']}").json()["status"] == "AVAILABLE"
    # now the second surgery can take it
    assert client.post(f"/api/v1/surgeries/{s2['id']}/schedule", json={"slotId": slot["id"]}).status_code == 200


def test_slot_too_short_and_wrong_department_and_unavailable_theatre(client):
    dept = create_department(client)
    other = create_department(client)
    theatre = create_theatre(client, dept["id"])
    short_slot = create_slot_ok(client, theatre["id"], minutes=30)
    patient = create_patient(client)
    long_surgery = create_surgery(client, patient["id"], dept["id"], duration=90)
    assert client.post(f"/api/v1/surgeries/{long_surgery['id']}/schedule", json={"slotId": short_slot["id"]}).status_code == 409

    other_patient = create_patient(client)
    other_surgery = create_surgery(client, other_patient["id"], other["id"], duration=15)
    assert client.post(f"/api/v1/surgeries/{other_surgery['id']}/schedule", json={"slotId": short_slot["id"]}).status_code == 409

    fitting = create_surgery(client, create_patient(client)["id"], dept["id"], duration=30)
    # theatre UNAVAILABLE blocks booking even though the slot is AVAILABLE (statuses are independent)
    client.patch(f"/api/v1/theatres/{theatre['id']}/status", json={"newStatus": "UNAVAILABLE"})
    assert client.get(f"/api/v1/theatre-slots/{short_slot['id']}").json()["status"] == "AVAILABLE"
    assert client.post(f"/api/v1/surgeries/{fitting['id']}/schedule", json={"slotId": short_slot["id"]}).status_code == 409
    client.patch(f"/api/v1/theatres/{theatre['id']}/status", json={"newStatus": "AVAILABLE", "autoAssign": False})
    assert client.post(f"/api/v1/surgeries/{fitting['id']}/schedule", json={"slotId": short_slot["id"]}).status_code == 200
    another = create_slot_ok(client, theatre["id"], now_utc() + timedelta(hours=8), minutes=60)
    assert client.post(f"/api/v1/surgeries/{fitting['id']}/schedule", json={"slotId": another["id"]}).status_code == 409  # already scheduled
    assert client.post(f"/api/v1/surgeries/{long_surgery['id']}/schedule", json={"slotId": 9999}).status_code == 404
