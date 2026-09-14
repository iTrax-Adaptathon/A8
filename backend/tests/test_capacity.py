from app.infrastructure.database.models import DepartmentModel, BedModel
from app.domain.enums import BedStatus


def test_capacity_intelligence(client, db_session):
    dept = DepartmentModel(name="ICU Unit", code="ICU")
    db_session.add(dept)
    db_session.commit()

    b1 = BedModel(bed_number="ICU-1", bed_type="ICU", department_id=dept.id, status=BedStatus.OCCUPIED.value)
    b2 = BedModel(bed_number="ICU-2", bed_type="ICU", department_id=dept.id, status=BedStatus.AVAILABLE.value)
    db_session.add_all([b1, b2])
    db_session.commit()

    res = client.get("/api/v1/capacity")
    assert res.status_code == 200
    metrics = res.json()
    assert metrics["total_beds"] == 2
    assert metrics["occupied_beds"] == 1
    assert metrics["available_beds"] == 1
    assert metrics["overall_occupancy_percentage"] == 50.0
    assert metrics["overall_alert_level"] == "NORMAL"
