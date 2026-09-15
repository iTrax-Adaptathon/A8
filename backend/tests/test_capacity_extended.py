"""Capacity: counts per resource group, department occupancy, updates after mutations,
and 'available' never including CLEANING / MAINTENANCE / inactive."""
from tests.helpers import (
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
    release_bed,
)


def _cap(client):
    res = client.get("/api/v1/capacity")
    assert res.status_code == 200, res.text
    return res.json()


def test_capacity_groups_and_department_occupancy(client):
    icu = create_department(client, name="ICU", code="ICU")
    surg = create_department(client, name="Surgical", code="SURG")
    beds = [create_bed(client, icu["id"], bed_type="ICU") for _ in range(4)]
    create_bed(client, surg["id"], bed_type="SURGICAL")
    client.patch(f"/api/v1/beds/{beds[2]['id']}/status", json={"newStatus": "CLEANING"})
    client.patch(f"/api/v1/beds/{beds[3]['id']}/status", json={"newStatus": "MAINTENANCE"})
    inactive = create_bed(client, icu["id"])
    client.delete(f"/api/v1/beds/{inactive['id']}")
    p1 = create_patient(client)
    admit(client, p1["id"], icu["id"], beds[0]["id"])

    theatre = create_theatre(client, surg["id"])
    cleaning_theatre = create_theatre(client, surg["id"], status="CLEANING")
    slot = create_slot_ok(client, theatre["id"], minutes=60)
    nurse = create_staff(client, icu["id"], role="NURSE")
    create_staff(client, icu["id"], role="NURSE", status="OFF_DUTY")
    surgeon = create_staff(client, surg["id"], role="SURGEON")
    waiting_patient = create_patient(client)
    add_waitlist(client, waiting_patient["id"], icu["id"])
    add_waitlist(client, create_patient(client)["id"], icu["id"], resource_type="STAFF", requiredStaffRole="NURSE")
    surgery = create_surgery(client, create_patient(client)["id"], surg["id"], duration=60)

    cap = _cap(client)
    assert cap["beds"] == {"total": 5, "available": 2, "occupied": 1, "cleaning": 1, "maintenance": 1}
    assert cap["totalBeds"] == 5 and cap["availableBeds"] == 2 and cap["occupiedBeds"] == 1
    assert cap["theatres"]["total"] == 2 and cap["theatres"]["available"] == 1 and cap["theatres"]["cleaning"] == 1
    assert cap["theatres"]["availableSlots"] == 1 and cap["theatres"]["bookedSlots"] == 0
    assert cap["theatres"]["nextAvailableSlot"] == slot["startTime"]
    assert cap["staff"] == {"total": 3, "available": 2, "assigned": 0, "offDuty": 1}
    assert cap["queues"] == {"waitingForBeds": 1, "waitingForTheatres": 1, "waitingForStaff": 1}
    icu_metrics = next(d for d in cap["departmentMetrics"] if d["departmentId"] == icu["id"])
    assert icu_metrics["totalBeds"] == 4 and icu_metrics["occupiedBeds"] == 1 and icu_metrics["availableBeds"] == 1
    assert icu_metrics["cleaningBeds"] == 1 and icu_metrics["maintenanceBeds"] == 1
    assert icu_metrics["occupancyPercentage"] == 25.0 and icu_metrics["alertLevel"] == "NORMAL"
    assert cap["generatedAt"].endswith("Z")

    # mutations are reflected immediately
    client.post(f"/api/v1/surgeries/{surgery['id']}/schedule", json={"slotId": slot["id"]})
    client.post(f"/api/v1/staff/{surgeon['id']}/assign", json={"assignmentType": "SURGERY", "surgeryId": surgery["id"]})
    client.post(f"/api/v1/staff/{nurse['id']}/assign", json={"assignmentType": "PATIENT", "patientId": p1["id"]})
    discharge(client, p1["id"])
    cap = _cap(client)
    assert cap["beds"]["occupied"] == 0 and cap["beds"]["cleaning"] == 2 and cap["beds"]["available"] == 2
    assert cap["theatres"]["bookedSlots"] == 1 and cap["theatres"]["availableSlots"] == 0 and cap["theatres"]["nextAvailableSlot"] is None
    assert cap["staff"]["assigned"] == 2 and cap["staff"]["available"] == 0
    assert cap["queues"]["waitingForTheatres"] == 0 and cap["queues"]["waitingForStaff"] == 1  # nurse went to p1, not the waiting patient

    # release -> auto-match admits the waiting patient: queue drops, occupancy rises
    release_bed(client, beds[0]["id"])
    cap = _cap(client)
    assert cap["queues"]["waitingForBeds"] == 0 and cap["beds"]["occupied"] == 1 and cap["beds"]["cleaning"] == 1


def test_alert_levels(client):
    dept = create_department(client)
    beds = [create_bed(client, dept["id"]) for _ in range(4)]
    for bed in beds[:3]:
        admit(client, create_patient(client)["id"], dept["id"], bed["id"])
    cap = _cap(client)
    assert cap["overallOccupancyPercentage"] == 75.0 and cap["overallAlertLevel"] == "HIGH_UTILIZATION"
    assert cap["highUtilizationDepartments"] == [dept["name"]]
    admit(client, create_patient(client)["id"], dept["id"], beds[3]["id"])
    cap = _cap(client)
    assert cap["overallAlertLevel"] == "CRITICAL_CAPACITY" and cap["criticalCapacityDepartments"] == [dept["name"]]


def test_department_endpoint_counts_only_active_beds(client):
    dept = create_department(client)
    b1 = create_bed(client, dept["id"])
    b2 = create_bed(client, dept["id"])
    client.delete(f"/api/v1/beds/{b2['id']}")
    admit(client, create_patient(client)["id"], dept["id"], b1["id"])
    d = client.get(f"/api/v1/departments/{dept['id']}").json()
    assert d["totalBeds"] == 1 and d["occupiedBeds"] == 1
