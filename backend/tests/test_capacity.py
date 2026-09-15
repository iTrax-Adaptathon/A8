from app.infrastructure.database.models import DepartmentModel, BedModel, PatientModel
from app.domain.enums import BedStatus, PatientStatus


def test_capacity_intelligence(client, db_session):
    dept = DepartmentModel(name="ICU Unit", code="ICU")
    db_session.add(dept)
    db_session.commit()

    patient = PatientModel(name="Occupant", age=60, gender="Female", medical_record_number="MRN-CAP-1",
                           current_status=PatientStatus.ADMITTED.value, current_department_id=dept.id)
    db_session.add(patient)
    db_session.commit()

    b1 = BedModel(bed_number="ICU-1", bed_type="ICU", department_id=dept.id, status=BedStatus.OCCUPIED.value,
                  current_patient_id=patient.id)
    b2 = BedModel(bed_number="ICU-2", bed_type="ICU", department_id=dept.id, status=BedStatus.AVAILABLE.value)
    db_session.add_all([b1, b2])
    db_session.commit()
    patient.current_bed_id = b1.id
    db_session.commit()

    res = client.get("/api/v1/capacity")
    assert res.status_code == 200
    metrics = res.json()
    assert metrics["totalBeds"] == 2
    assert metrics["occupiedBeds"] == 1
    assert metrics["availableBeds"] == 1
    assert metrics["overallOccupancyPercentage"] == 50.0
    assert metrics["overallAlertLevel"] == "NORMAL"
