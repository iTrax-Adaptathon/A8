from app.infrastructure.database.models import DepartmentModel


def test_bed_management(client, db_session):
    dept = DepartmentModel(name="Emergency Dept", code="ER")
    db_session.add(dept)
    db_session.commit()

    bed_payload = {
        "bed_number": "ER-01",
        "bed_type": "EMERGENCY",
        "department_id": dept.id,
        "status": "AVAILABLE",
    }
    create_res = client.post("/api/v1/beds", json=bed_payload)
    assert create_res.status_code == 201
    bed_data = create_res.json()
    assert bed_data["bedNumber"] == "ER-01"

    avail_res = client.get("/api/v1/beds/available")
    assert avail_res.status_code == 200
    assert len(avail_res.json()) == 1
