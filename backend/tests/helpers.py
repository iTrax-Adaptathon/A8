"""API-level factories shared by the test modules."""
from datetime import datetime, timedelta, timezone

ACTOR = {"X-Actor-ID": "nurse-7", "X-Actor-Name": "Nurse Seven"}


def now_utc():
    return datetime.now(timezone.utc).replace(tzinfo=None)


def iso(dt: datetime) -> str:
    return dt.replace(microsecond=0).isoformat() + "Z"


_counter = {"n": 0}


def _next() -> int:
    _counter["n"] += 1
    return _counter["n"]


def create_department(client, name=None, code=None):
    n = _next()
    res = client.post("/api/v1/departments", json={"name": name or f"Dept {n}", "code": code or f"D{n}"})
    assert res.status_code == 201, res.text
    return res.json()


def create_bed(client, department_id, bed_number=None, bed_type="GENERAL", status="AVAILABLE"):
    n = _next()
    res = client.post(
        "/api/v1/beds",
        json={"bedNumber": bed_number or f"BED-{n}", "bedType": bed_type, "departmentId": department_id, "status": status},
    )
    assert res.status_code == 201, res.text
    return res.json()


def create_patient(client, name=None, mrn=None, age=40, gender="Female"):
    n = _next()
    res = client.post(
        "/api/v1/patients",
        json={"name": name or f"Patient {n}", "age": age, "gender": gender, "medicalRecordNumber": mrn or f"MRN-{n}"},
    )
    assert res.status_code == 201, res.text
    return res.json()


def admit(client, patient_id, department_id, bed_id, headers=None, notes="Admitted"):
    return client.post(
        f"/api/v1/patients/{patient_id}/admit",
        json={"departmentId": department_id, "bedId": bed_id, "notes": notes},
        headers=headers or {},
    )


def transfer(client, patient_id, department_id, bed_id, headers=None):
    return client.post(
        f"/api/v1/patients/{patient_id}/transfer",
        json={"targetDepartmentId": department_id, "targetBedId": bed_id},
        headers=headers or {},
    )


def discharge(client, patient_id, headers=None):
    return client.post(f"/api/v1/patients/{patient_id}/discharge", json={"notes": "Done"}, headers=headers or {})


def release_bed(client, bed_id, auto_assign=None, headers=None):
    body = {"notes": "cleaned"}
    if auto_assign is not None:
        body["autoAssign"] = auto_assign
    return client.post(f"/api/v1/beds/{bed_id}/release", json=body, headers=headers or {})


def create_theatre(client, department_id, name=None, status="AVAILABLE"):
    n = _next()
    res = client.post("/api/v1/theatres", json={"name": name or f"Theatre {n}", "departmentId": department_id, "status": status})
    assert res.status_code == 201, res.text
    return res.json()


def create_slot(client, theatre_id, start=None, minutes=120, auto_assign=False):
    start = start or (now_utc() + timedelta(hours=2))
    res = client.post(
        "/api/v1/theatre-slots",
        json={"theatreId": theatre_id, "startTime": iso(start), "endTime": iso(start + timedelta(minutes=minutes)), "autoAssign": auto_assign},
    )
    return res


def create_slot_ok(client, theatre_id, start=None, minutes=120, auto_assign=False):
    res = create_slot(client, theatre_id, start, minutes, auto_assign)
    assert res.status_code == 201, res.text
    return res.json()["slot"]


def create_surgery(client, patient_id, department_id, duration=60, priority=3, required_role=None, name="Procedure"):
    body = {"patientId": patient_id, "departmentId": department_id, "procedureName": name, "durationMinutes": duration, "priority": priority}
    if required_role:
        body["requiredStaffRole"] = required_role
    res = client.post("/api/v1/surgeries", json=body)
    assert res.status_code == 201, res.text
    return res.json()


def create_staff(client, department_id, role="NURSE", name=None, status="AVAILABLE", shift_hours=(-2, 10)):
    n = _next()
    start = now_utc() + timedelta(hours=shift_hours[0])
    end = now_utc() + timedelta(hours=shift_hours[1])
    res = client.post(
        "/api/v1/staff",
        json={
            "name": name or f"Staff {n}",
            "role": role,
            "departmentId": department_id,
            "shiftStart": iso(start),
            "shiftEnd": iso(end),
            "status": status,
        },
    )
    assert res.status_code == 201, res.text
    return res.json()


def add_waitlist(client, patient_id, department_id, resource_type="BED", priority=3, **extra):
    body = {"patientId": patient_id, "departmentId": department_id, "resourceType": resource_type, "priority": priority}
    body.update(extra)
    return client.post("/api/v1/waitlist", json=body)


def events(client, **filters):
    res = client.get("/api/v1/flow-events", params={k: v for k, v in filters.items() if v is not None} | {"limit": 500})
    assert res.status_code == 200, res.text
    return res.json()


def event_types(client, **filters):
    return [e["eventType"] for e in events(client, **filters)]
