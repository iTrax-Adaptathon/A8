"""The demo seed must produce a consistent, rule-abiding database."""
from sqlalchemy import text
from sqlalchemy.orm import sessionmaker

import scripts.seed_data as seed
from app.infrastructure.database import build_engine
from app.infrastructure.database.models import (
    BedModel,
    FlowEventModel,
    PatientModel,
    StaffAssignmentModel,
    StaffModel,
    SurgeryModel,
    TheatreModel,
    TheatreSlotModel,
    WaitlistEntryModel,
)


def test_seed_is_consistent(tmp_path, monkeypatch):
    engine = build_engine(f"sqlite:///{tmp_path / 'seed.db'}")
    monkeypatch.setattr(seed, "engine", engine)
    monkeypatch.setattr(seed, "SessionLocal", sessionmaker(bind=engine, autoflush=False))
    seed.seed_database()

    with sessionmaker(bind=engine)() as db:
        assert db.execute(text("PRAGMA foreign_keys")).scalar() == 1
        beds = db.query(BedModel).all()
        patients = db.query(PatientModel).all()
        statuses = {b.status for b in beds}
        assert statuses == {"AVAILABLE", "OCCUPIED", "CLEANING", "MAINTENANCE"}
        for bed in beds:
            assert (bed.status == "OCCUPIED") == (bed.current_patient_id is not None)
            if bed.current_patient_id is not None:
                assert db.get(PatientModel, bed.current_patient_id).current_bed_id == bed.id
        assert {p.current_status for p in patients} == {"REGISTERED", "ADMITTED", "TRANSFERRED", "DISCHARGED"}
        for p in patients:
            if p.current_bed_id is not None:
                bed = db.get(BedModel, p.current_bed_id)
                assert bed.status == "OCCUPIED" and bed.current_patient_id == p.id
                assert p.current_status in ("ADMITTED", "TRANSFERRED")
            else:
                assert p.current_status in ("REGISTERED", "DISCHARGED")

        theatres = db.query(TheatreModel).all()
        assert {t.status for t in theatres} == {"AVAILABLE", "IN_USE", "CLEANING", "UNAVAILABLE"}
        slots = db.query(TheatreSlotModel).all()
        assert {s.status for s in slots} == {"AVAILABLE", "BOOKED", "COMPLETED", "CANCELLED"}
        for s in slots:
            if s.status in ("BOOKED", "COMPLETED"):
                surgery = db.get(SurgeryModel, s.surgery_id)
                assert surgery.slot_id == s.id and surgery.theatre_id == s.theatre_id
            else:
                assert s.surgery_id is None
        surgeries = db.query(SurgeryModel).all()
        assert {s.status for s in surgeries} >= {"WAITING", "SCHEDULED", "IN_PROGRESS", "COMPLETED", "CANCELLED"}

        staff = db.query(StaffModel).all()
        assert {s.status for s in staff} == {"AVAILABLE", "ASSIGNED", "OFF_DUTY"}
        for s in staff:
            active = db.query(StaffAssignmentModel).filter_by(staff_id=s.id, status="ACTIVE").count()
            assert (s.status == "ASSIGNED") == (active == 1)
            assert active <= 1

        waiting = db.query(WaitlistEntryModel).filter_by(status="WAITING").all()
        assert {w.resource_type for w in waiting} == {"BED", "THEATRE", "STAFF"}
        waiting_surgeries = {s.id for s in surgeries if s.status == "WAITING"}
        assert {w.surgery_id for w in waiting if w.resource_type == "THEATRE"} == waiting_surgeries

        events = db.query(FlowEventModel).all()
        assert len(events) > 50
        assert all(e.actor_id and e.actor_name for e in events)
        assert {e.source for e in events} == {"SEED", "AUTO_MATCH"}
        assert any(e.event_type == "TRANSFER" for e in events) and any(e.event_type == "DISCHARGE" for e in events)
    engine.dispose()


def test_seed_serves_through_the_api(tmp_path, monkeypatch):
    from fastapi.testclient import TestClient
    from app.infrastructure.database import get_db
    from app.main import app

    engine = build_engine(f"sqlite:///{tmp_path / 'seed_api.db'}")
    Session = sessionmaker(bind=engine, autoflush=False)
    monkeypatch.setattr(seed, "engine", engine)
    monkeypatch.setattr(seed, "SessionLocal", Session)
    seed.seed_database()

    def override():
        db = Session()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override
    try:
        with TestClient(app) as client:
            cap = client.get("/api/v1/capacity").json()
            assert cap["beds"]["total"] == 45 and cap["beds"]["occupied"] == 23
            assert cap["beds"]["cleaning"] == 4 and cap["beds"]["maintenance"] == 2 and cap["beds"]["available"] == 16
            assert cap["theatres"] == cap["theatres"] | {"total": 4, "available": 1, "inUse": 1, "cleaning": 1, "unavailable": 1}
            assert cap["staff"]["total"] == 23 and cap["staff"]["assigned"] == 6 and cap["staff"]["offDuty"] == 5
            assert cap["queues"] == {"waitingForBeds": 4, "waitingForTheatres": 3, "waitingForStaff": 2}
            assert cap["theatres"]["nextAvailableSlot"]
            queue = client.get("/api/v1/waitlist", params={"resourceType": "BED"}).json()
            assert [q["priority"] for q in queue] == [1, 2, 2, 3]
            assert queue[1]["requestedAt"] < queue[2]["requestedAt"]  # longest wait first within priority 2
            first_patient = client.get("/api/v1/patients?limit=1").json()[0]
            assert client.get(f"/api/v1/patients/{first_patient['id']}/history").status_code == 200
            # a matching preview on the free Theatre 1 slot finds the waiting surgeries that fit
            slots = client.get("/api/v1/theatre-slots", params={"status": "AVAILABLE"}).json()
            t1 = next(t for t in client.get("/api/v1/theatres").json() if t["name"] == "Theatre 1")
            free = next(s for s in slots if s["theatreId"] == t1["id"])
            match = client.get("/api/v1/matches", params={"resourceType": "THEATRE_SLOT", "resourceId": free["id"]}).json()
            assert match["resourceAvailable"] is True and len(match["candidates"]) >= 1
    finally:
        app.dependency_overrides.clear()
        engine.dispose()
