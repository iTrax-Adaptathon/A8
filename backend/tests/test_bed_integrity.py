"""Bed integrity: occupied beds can never be freed incorrectly; release workflow;
duplicate assignment; consistency of bed <-> patient references."""
from app.infrastructure.database.models import BedModel, PatientModel
from tests.helpers import admit, create_bed, create_department, create_patient, discharge, release_bed, transfer


def _setup(client):
    dept = create_department(client)
    bed = create_bed(client, dept["id"])
    patient = create_patient(client)
    assert admit(client, patient["id"], dept["id"], bed["id"]).status_code == 200
    return dept, bed, patient


def test_occupied_bed_cannot_be_set_available_directly(client):
    dept, bed, patient = _setup(client)
    res = client.patch(f"/api/v1/beds/{bed['id']}/status", json={"newStatus": "AVAILABLE"})
    assert res.status_code == 409
    assert res.json()["error"] == "CONFLICT"
    bed_after = client.get(f"/api/v1/beds/{bed['id']}").json()
    assert bed_after["status"] == "OCCUPIED"
    assert bed_after["currentPatientId"] == patient["id"]
    assert client.get(f"/api/v1/patients/{patient['id']}").json()["currentBedId"] == bed["id"]


def test_occupied_bed_cannot_be_set_cleaning_or_maintenance_directly(client):
    dept, bed, patient = _setup(client)
    for target in ("CLEANING", "MAINTENANCE"):
        res = client.patch(f"/api/v1/beds/{bed['id']}/status", json={"newStatus": target})
        assert res.status_code == 409, target


def test_bed_cannot_be_set_occupied_manually(client):
    dept = create_department(client)
    bed = create_bed(client, dept["id"])
    res = client.patch(f"/api/v1/beds/{bed['id']}/status", json={"newStatus": "OCCUPIED"})
    assert res.status_code == 409


def test_bed_cannot_be_created_occupied(client):
    dept = create_department(client)
    res = client.post("/api/v1/beds", json={"bedNumber": "X-1", "bedType": "GENERAL", "departmentId": dept["id"], "status": "OCCUPIED"})
    assert res.status_code == 422
    assert res.json()["error"] == "DOMAIN_VALIDATION_ERROR"


def test_valid_release_workflow_occupied_cleaning_available(client):
    dept, bed, patient = _setup(client)
    assert discharge(client, patient["id"]).status_code == 200
    assert client.get(f"/api/v1/beds/{bed['id']}").json()["status"] == "CLEANING"

    # Release is only valid from CLEANING
    res = release_bed(client, bed["id"], auto_assign=False)
    assert res.status_code == 200, res.text
    assert res.json()["bed"]["status"] == "AVAILABLE"
    assert res.json()["bed"]["currentPatientId"] is None
    assert res.json()["autoAssignment"] is None

    # Releasing an AVAILABLE bed again is a conflict
    assert release_bed(client, bed["id"], auto_assign=False).status_code == 409


def test_release_rejected_for_maintenance_and_occupied(client):
    dept = create_department(client)
    bed = create_bed(client, dept["id"])
    assert client.patch(f"/api/v1/beds/{bed['id']}/status", json={"newStatus": "MAINTENANCE"}).status_code == 200
    assert release_bed(client, bed["id"]).status_code == 409
    assert client.patch(f"/api/v1/beds/{bed['id']}/status", json={"newStatus": "AVAILABLE"}).status_code == 200
    patient = create_patient(client)
    assert admit(client, patient["id"], dept["id"], bed["id"]).status_code == 200
    assert release_bed(client, bed["id"]).status_code == 409


def test_manual_transitions_between_non_occupied_states(client):
    dept = create_department(client)
    bed = create_bed(client, dept["id"])
    for target, expected in (
        ("CLEANING", 200),
        ("MAINTENANCE", 200),
        ("MAINTENANCE", 409),  # same status
        ("CLEANING", 200),
        ("AVAILABLE", 200),
    ):
        res = client.patch(f"/api/v1/beds/{bed['id']}/status", json={"newStatus": target})
        assert res.status_code == expected, (target, res.text)


def test_duplicate_assignment_of_same_bed_is_rejected(client):
    dept, bed, patient = _setup(client)
    other = create_patient(client)
    res = admit(client, other["id"], dept["id"], bed["id"])
    assert res.status_code == 409
    assert client.get(f"/api/v1/patients/{other['id']}").json()["currentStatus"] == "REGISTERED"
    assert client.get(f"/api/v1/beds/{bed['id']}").json()["currentPatientId"] == patient["id"]


def test_patient_cannot_hold_two_beds(client):
    dept, bed, patient = _setup(client)
    bed2 = create_bed(client, dept["id"])
    # A second admission of an admitted patient is an invalid transition
    assert admit(client, patient["id"], dept["id"], bed2["id"]).status_code == 409
    assert client.get(f"/api/v1/beds/{bed2['id']}").json()["status"] == "AVAILABLE"


def test_transfer_into_same_bed_and_into_non_available_bed(client):
    dept, bed, patient = _setup(client)
    assert transfer(client, patient["id"], dept["id"], bed["id"]).status_code == 409
    bed2 = create_bed(client, dept["id"])
    client.patch(f"/api/v1/beds/{bed2['id']}/status", json={"newStatus": "CLEANING"})
    assert transfer(client, patient["id"], dept["id"], bed2["id"]).status_code == 409
    assert client.get(f"/api/v1/patients/{patient['id']}").json()["currentBedId"] == bed["id"]


def test_bed_in_wrong_department_is_rejected(client):
    dept_a = create_department(client)
    dept_b = create_department(client)
    bed_b = create_bed(client, dept_b["id"])
    patient = create_patient(client)
    assert admit(client, patient["id"], dept_a["id"], bed_b["id"]).status_code == 409


def test_inactive_bed_cannot_be_assigned(client):
    dept = create_department(client)
    bed = create_bed(client, dept["id"])
    assert client.delete(f"/api/v1/beds/{bed['id']}").status_code == 200
    patient = create_patient(client)
    assert admit(client, patient["id"], dept["id"], bed["id"]).status_code == 409
    assert client.get("/api/v1/beds").json() == []
    assert len(client.get("/api/v1/beds?includeInactive=true").json()) == 1


def test_database_constraint_blocks_occupied_bed_without_patient(client, db_session):
    """The CHECK constraint is the last line of defence."""
    import pytest
    from sqlalchemy.exc import IntegrityError

    dept = create_department(client)
    bed = create_bed(client, dept["id"])
    model = db_session.get(BedModel, bed["id"])
    model.status = "OCCUPIED"
    with pytest.raises(IntegrityError):
        db_session.commit()
    db_session.rollback()


def test_database_constraint_blocks_two_beds_for_one_patient(client, db_session):
    import pytest
    from sqlalchemy.exc import IntegrityError

    dept, bed, patient = _setup(client)
    bed2 = create_bed(client, dept["id"])
    model = db_session.get(BedModel, bed2["id"])
    model.status = "OCCUPIED"
    model.current_patient_id = patient["id"]
    with pytest.raises(IntegrityError):
        db_session.commit()
    db_session.rollback()
