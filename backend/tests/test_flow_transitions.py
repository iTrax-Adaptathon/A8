"""Patient flow: admit / transfer / discharge and impossible states."""
from tests.helpers import admit, create_bed, create_department, create_patient, discharge, transfer


def test_admit_transfer_discharge_happy_path(client):
    dept_a = create_department(client)
    dept_b = create_department(client)
    bed_a = create_bed(client, dept_a["id"])
    bed_b = create_bed(client, dept_b["id"])
    patient = create_patient(client)

    res = admit(client, patient["id"], dept_a["id"], bed_a["id"])
    assert res.status_code == 200
    body = res.json()
    assert body["currentStatus"] == "ADMITTED" and body["currentBedId"] == bed_a["id"] and body["admittedAt"]
    assert client.get(f"/api/v1/beds/{bed_a['id']}").json()["currentPatientId"] == patient["id"]

    res = transfer(client, patient["id"], dept_b["id"], bed_b["id"])
    assert res.status_code == 200
    assert res.json()["currentStatus"] == "TRANSFERRED" and res.json()["currentDepartmentId"] == dept_b["id"]
    assert client.get(f"/api/v1/beds/{bed_a['id']}").json()["status"] == "CLEANING"
    assert client.get(f"/api/v1/beds/{bed_b['id']}").json()["currentPatientId"] == patient["id"]

    res = discharge(client, patient["id"])
    assert res.status_code == 200
    assert res.json()["currentStatus"] == "DISCHARGED" and res.json()["currentBedId"] is None and res.json()["dischargedAt"]
    assert client.get(f"/api/v1/beds/{bed_b['id']}").json()["status"] == "CLEANING"


def test_discharged_patient_cannot_transfer_or_be_readmitted(client):
    dept = create_department(client)
    bed = create_bed(client, dept["id"])
    bed2 = create_bed(client, dept["id"])
    patient = create_patient(client)
    admit(client, patient["id"], dept["id"], bed["id"])
    discharge(client, patient["id"])
    assert transfer(client, patient["id"], dept["id"], bed2["id"]).status_code == 409
    assert admit(client, patient["id"], dept["id"], bed2["id"]).status_code == 409
    assert discharge(client, patient["id"]).status_code == 409
    assert client.get(f"/api/v1/beds/{bed2['id']}").json()["status"] == "AVAILABLE"


def test_registered_patient_cannot_transfer_or_discharge(client):
    dept = create_department(client)
    bed = create_bed(client, dept["id"])
    patient = create_patient(client)
    assert transfer(client, patient["id"], dept["id"], bed["id"]).status_code == 409
    assert discharge(client, patient["id"]).status_code == 409


def test_transfer_twice_is_allowed_and_beds_follow(client):
    dept = create_department(client)
    beds = [create_bed(client, dept["id"]) for _ in range(3)]
    patient = create_patient(client)
    admit(client, patient["id"], dept["id"], beds[0]["id"])
    assert transfer(client, patient["id"], dept["id"], beds[1]["id"]).status_code == 200
    assert transfer(client, patient["id"], dept["id"], beds[2]["id"]).status_code == 200
    statuses = [client.get(f"/api/v1/beds/{b['id']}").json()["status"] for b in beds]
    assert statuses == ["CLEANING", "CLEANING", "OCCUPIED"]


def test_unknown_ids_return_404(client):
    dept = create_department(client)
    bed = create_bed(client, dept["id"])
    patient = create_patient(client)
    assert admit(client, 9999, dept["id"], bed["id"]).status_code == 404
    assert admit(client, patient["id"], 9999, bed["id"]).status_code == 404
    assert admit(client, patient["id"], dept["id"], 9999).status_code == 404
    assert client.get("/api/v1/patients/9999").status_code == 404
    assert client.get("/api/v1/beds/9999").status_code == 404
    assert client.get("/api/v1/departments/9999").status_code == 404


def test_failed_admission_writes_nothing(client):
    dept = create_department(client)
    bed = create_bed(client, dept["id"])
    p1 = create_patient(client)
    p2 = create_patient(client)
    admit(client, p1["id"], dept["id"], bed["id"])
    before = client.get("/api/v1/flow-events?limit=500").headers["X-Total-Count"]
    assert admit(client, p2["id"], dept["id"], bed["id"]).status_code == 409
    after = client.get("/api/v1/flow-events?limit=500").headers["X-Total-Count"]
    assert before == after
    assert client.get(f"/api/v1/patients/{p2['id']}").json()["currentStatus"] == "REGISTERED"
