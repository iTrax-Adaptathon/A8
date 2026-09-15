"""Concurrent resource claims on a real file-backed SQLite database.

Two threads, each with its own session/transaction, try to claim the same
resource at the same moment. Exactly one must succeed; the database must be
consistent afterwards.
"""
import threading
from datetime import timedelta

import pytest
from sqlalchemy.orm import sessionmaker

from app.domain.entities import Bed, Department, Patient, Staff, Surgery, Theatre, TheatreSlot
from app.domain.enums import BedType, PatientStatus, StaffAssignmentType, StaffRole, StaffStatus
from app.domain.policies import ConflictError, DomainValidationError, utc_now
from app.infrastructure.database import Base, build_engine
from app.infrastructure.database.models import BedModel, PatientModel, StaffAssignmentModel, StaffModel, TheatreSlotModel
from app.infrastructure.repositories import (
    BedRepository,
    DepartmentRepository,
    FlowEventRepository,
    PatientRepository,
    StaffRepository,
    SurgeryRepository,
    TheatreRepository,
    TheatreSlotRepository,
    WaitlistRepository,
)
from app.application.staff_service import StaffService
from app.application.surgery_service import SurgeryService
from app.orchestration.flow_orchestration_service import FlowOrchestrationService


@pytest.fixture
def file_engine(tmp_path):
    engine = build_engine(f"sqlite:///{tmp_path / 'concurrency.db'}")
    Base.metadata.create_all(bind=engine)
    yield engine
    engine.dispose()


def _flow(db):
    return FlowOrchestrationService(
        PatientRepository(db), BedRepository(db), DepartmentRepository(db), FlowEventRepository(db), WaitlistRepository(db)
    )


def _run_concurrently(workers):
    """Run callables in parallel threads, synchronised on a barrier. Returns list of (ok, error)."""
    barrier = threading.Barrier(len(workers))
    results = [None] * len(workers)

    def run(i, fn):
        try:
            barrier.wait(timeout=10)
            fn()
            results[i] = (True, None)
        except Exception as exc:  # noqa: BLE001 - we want every failure type
            results[i] = (False, exc)

    threads = [threading.Thread(target=run, args=(i, fn)) for i, fn in enumerate(workers)]
    for t in threads:
        t.start()
    for t in threads:
        t.join(timeout=60)
    return results


def test_two_simultaneous_admissions_same_bed_exactly_one_succeeds(file_engine):
    Session = sessionmaker(bind=file_engine, autoflush=False)
    with Session() as db:
        dept = DepartmentRepository(db).create(Department(id=None, name="ICU", code="ICU"))
        bed = BedRepository(db).create(Bed(id=None, bed_number="ICU-1", bed_type=BedType.ICU, department_id=dept.id))
        p1 = PatientRepository(db).create(Patient(id=None, name="A", age=30, gender="F", medical_record_number="C-1"))
        p2 = PatientRepository(db).create(Patient(id=None, name="B", age=31, gender="M", medical_record_number="C-2"))
        db.commit()
        dept_id, bed_id, p1_id, p2_id = dept.id, bed.id, p1.id, p2.id

    def admit(patient_id):
        def work():
            with Session() as db:
                _flow(db).admit_patient(patient_id, dept_id, bed_id)
        return work

    for _round in range(3):  # repeat to shake out timing luck
        # reset
        with Session() as db:
            db.query(BedModel).filter(BedModel.id == bed_id).update({"status": "AVAILABLE", "current_patient_id": None})
            db.query(PatientModel).update({"current_status": PatientStatus.REGISTERED.value, "current_bed_id": None, "current_department_id": None})
            db.commit()

        results = _run_concurrently([admit(p1_id), admit(p2_id)])
        successes = [r for r in results if r[0]]
        failures = [r for r in results if not r[0]]
        assert len(successes) == 1, results
        assert len(failures) == 1 and isinstance(failures[0][1], ConflictError), failures

        with Session() as db:
            bed_row = db.get(BedModel, bed_id)
            assert bed_row.status == "OCCUPIED"
            occupants = db.query(PatientModel).filter(PatientModel.current_bed_id == bed_id).all()
            assert len(occupants) == 1
            assert bed_row.current_patient_id == occupants[0].id
            assert occupants[0].current_status == PatientStatus.ADMITTED.value
            others = db.query(PatientModel).filter(PatientModel.current_bed_id.is_(None)).all()
            assert len(others) == 1 and others[0].current_status == PatientStatus.REGISTERED.value


def test_two_simultaneous_bookings_same_slot_exactly_one_succeeds(file_engine):
    Session = sessionmaker(bind=file_engine, autoflush=False)
    with Session() as db:
        dept = DepartmentRepository(db).create(Department(id=None, name="Surgical", code="SURG"))
        theatre = TheatreRepository(db).create(Theatre(id=None, name="T1", department_id=dept.id))
        start = utc_now() + timedelta(hours=3)
        slot = TheatreSlotRepository(db).create(TheatreSlot(id=None, theatre_id=theatre.id, start_time=start, end_time=start + timedelta(hours=2)))
        patients = [PatientRepository(db).create(Patient(id=None, name=f"P{i}", age=40, gender="F", medical_record_number=f"S-{i}")) for i in range(2)]
        surgeries = []
        for p in patients:
            surgeries.append(SurgeryRepository(db).create(Surgery(id=None, patient_id=p.id, department_id=dept.id, procedure_name="Op", duration_minutes=60)))
        db.commit()
        slot_id = slot.id
        surgery_ids = [s.id for s in surgeries]

    def book(surgery_id):
        def work():
            with Session() as db:
                SurgeryService(SurgeryRepository(db)).schedule_surgery(surgery_id, slot_id)
        return work

    results = _run_concurrently([book(surgery_ids[0]), book(surgery_ids[1])])
    assert sum(1 for ok, _ in results if ok) == 1, results
    assert all(isinstance(err, ConflictError) for ok, err in results if not ok), results
    with Session() as db:
        row = db.get(TheatreSlotModel, slot_id)
        assert row.status == "BOOKED" and row.surgery_id in surgery_ids
        scheduled = [s for s in SurgeryRepository(db).get_all() if s.slot_id == slot_id]
        assert len(scheduled) == 1


def test_two_simultaneous_staff_assignments_exactly_one_succeeds(file_engine):
    Session = sessionmaker(bind=file_engine, autoflush=False)
    with Session() as db:
        dept = DepartmentRepository(db).create(Department(id=None, name="Cardio", code="CARD"))
        now = utc_now()
        staff = StaffRepository(db).create(Staff(id=None, name="N1", role=StaffRole.NURSE, department_id=dept.id,
                                                 shift_start=now - timedelta(hours=1), shift_end=now + timedelta(hours=8)))
        bed = BedRepository(db).create(Bed(id=None, bed_number="C-1", bed_type=BedType.GENERAL, department_id=dept.id))
        bed2 = BedRepository(db).create(Bed(id=None, bed_number="C-2", bed_type=BedType.GENERAL, department_id=dept.id))
        p1 = PatientRepository(db).create(Patient(id=None, name="A", age=30, gender="F", medical_record_number="N-1"))
        p2 = PatientRepository(db).create(Patient(id=None, name="B", age=30, gender="F", medical_record_number="N-2"))
        db.commit()
        _flow(db).admit_patient(p1.id, dept.id, bed.id)
        _flow(db).admit_patient(p2.id, dept.id, bed2.id)
        staff_id, p1_id, p2_id = staff.id, p1.id, p2.id

    def assign(patient_id):
        def work():
            with Session() as db:
                StaffService(StaffRepository(db)).assign_staff(staff_id, StaffAssignmentType.PATIENT, patient_id=patient_id)
        return work

    results = _run_concurrently([assign(p1_id), assign(p2_id)])
    assert sum(1 for ok, _ in results if ok) == 1, results
    assert all(isinstance(err, DomainValidationError) for ok, err in results if not ok), results
    with Session() as db:
        assert db.get(StaffModel, staff_id).status == StaffStatus.ASSIGNED.value
        active = db.query(StaffAssignmentModel).filter(StaffAssignmentModel.status == "ACTIVE").all()
        assert len(active) == 1
