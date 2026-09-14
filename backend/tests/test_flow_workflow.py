from app.infrastructure.database.models import DepartmentModel, BedModel
from app.domain.enums import BedStatus


def test_full_patient_flow_workflow(client, db_session):
    # 1. Setup 2 Departments and 2 Beds
    er_dept = DepartmentModel(name="Emergency", code="ER")
    icu_dept = DepartmentModel(name="ICU", code="ICU")
    db_session.add_all([er_dept, icu_dept])
    db_session.commit()

    er_bed = BedModel(bed_number="ER-101", bed_type="EMERGENCY", department_id=er_dept.id, status=BedStatus.AVAILABLE.value)
    icu_bed = BedModel(bed_number="ICU-101", bed_type="ICU", department_id=icu_dept.id, status=BedStatus.AVAILABLE.value)
    db_session.add_all([er_bed, icu_bed])
    db_session.commit()

    # 2. Create Patient
    p_res = client.post("/api/v1/patients", json={
        "name": "Full Flow Patient",
        "age": 50,
        "gender": "Male",
        "medical_record_number": "MRN-FLOW-1",
    })
    assert p_res.status_code == 201
    patient_id = p_res.json()["id"]

    # 3. Admit Patient to ER
    admit_res = client.post(f"/api/v1/patients/{patient_id}/admit", json={
        "department_id": er_dept.id,
        "bed_id": er_bed.id,
        "notes": "Admitted to ER",
    })
    assert admit_res.status_code == 200
    assert admit_res.json()["current_status"] == "ADMITTED"

    # Check capacity after admission
    cap1 = client.get("/api/v1/capacity").json()
    assert cap1["occupied_beds"] == 1

    # 4. Transfer Patient to ICU
    transfer_res = client.post(f"/api/v1/patients/{patient_id}/transfer", json={
        "target_department_id": icu_dept.id,
        "target_bed_id": icu_bed.id,
        "notes": "Transferred to ICU",
    })
    assert transfer_res.status_code == 200
    assert transfer_res.json()["current_status"] == "TRANSFERRED"
    assert transfer_res.json()["current_department_id"] == icu_dept.id

    # Verify ER Bed was set to CLEANING upon transfer
    er_bed_updated = client.get(f"/api/v1/beds/{er_bed.id}").json()
    assert er_bed_updated["status"] == "CLEANING"

    # 5. Check Flow Events Log
    events_res = client.get(f"/api/v1/flow-events?patient_id={patient_id}")
    assert events_res.status_code == 200
    events = events_res.json()
    assert len(events) >= 2  # ADMISSION and TRANSFER

    # 6. Discharge Patient
    discharge_res = client.post(f"/api/v1/patients/{patient_id}/discharge", json={
        "notes": "Discharged from ICU",
    })
    assert discharge_res.status_code == 200
    assert discharge_res.json()["current_status"] == "DISCHARGED"

    # Verify ICU bed was released back to AVAILABLE
    icu_bed_updated = client.get(f"/api/v1/beds/{icu_bed.id}").json()
    assert icu_bed_updated["status"] == "AVAILABLE"
