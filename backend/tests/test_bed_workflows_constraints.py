"""Admit / transfer / discharge / release on a file-backed SQLite with
PRAGMA foreign_keys=ON and every constraint enabled: each workflow must
succeed atomically and leave a consistent bed <-> patient state."""
from sqlalchemy import text
from sqlalchemy.orm import sessionmaker

from app.domain.entities import Bed, Department, Patient
from app.domain.enums import BedStatus, BedType, PatientStatus
from app.infrastructure.database import Base, build_engine
from app.infrastructure.database.models import BedModel, FlowEventModel, PatientModel
from app.infrastructure.repositories import (
    BedRepository,
    DepartmentRepository,
    FlowEventRepository,
    PatientRepository,
    WaitlistRepository,
)
from app.orchestration.flow_orchestration_service import FlowOrchestrationService


def _flow(db):
    return FlowOrchestrationService(
        PatientRepository(db), BedRepository(db), DepartmentRepository(db), FlowEventRepository(db), WaitlistRepository(db)
    )


def _assert_consistent(db):
    beds = db.query(BedModel).all()
    patients = db.query(PatientModel).all()
    for bed in beds:
        assert (bed.status == BedStatus.OCCUPIED.value) == (bed.current_patient_id is not None)
        if bed.current_patient_id is not None:
            occupant = db.get(PatientModel, bed.current_patient_id)
            assert occupant.current_bed_id == bed.id
    for patient in patients:
        if patient.current_bed_id is not None:
            bed = db.get(BedModel, patient.current_bed_id)
            assert bed.status == BedStatus.OCCUPIED.value and bed.current_patient_id == patient.id
            assert patient.current_status in (PatientStatus.ADMITTED.value, PatientStatus.TRANSFERRED.value)
        else:
            assert patient.current_status in (PatientStatus.REGISTERED.value, PatientStatus.DISCHARGED.value)


def test_full_workflow_with_all_constraints(tmp_path):
    engine = build_engine(f"sqlite:///{tmp_path / 'flow.db'}")
    Base.metadata.create_all(bind=engine)
    Session = sessionmaker(bind=engine, autoflush=False)

    with Session() as db:
        assert db.execute(text("PRAGMA foreign_keys")).scalar() == 1
        er = DepartmentRepository(db).create(Department(id=None, name="ER", code="ER"))
        icu = DepartmentRepository(db).create(Department(id=None, name="ICU", code="ICU"))
        er_bed = BedRepository(db).create(Bed(id=None, bed_number="ER-1", bed_type=BedType.EMERGENCY, department_id=er.id))
        icu_bed = BedRepository(db).create(Bed(id=None, bed_number="ICU-1", bed_type=BedType.ICU, department_id=icu.id))
        patient = PatientRepository(db).create(Patient(id=None, name="Flow", age=50, gender="M", medical_record_number="F-1"))
        db.commit()
        ids = (er.id, icu.id, er_bed.id, icu_bed.id, patient.id)

    er_id, icu_id, er_bed_id, icu_bed_id, patient_id = ids

    with Session() as db:
        p = _flow(db).admit_patient(patient_id, er_id, er_bed_id)
        assert p.current_status == PatientStatus.ADMITTED and p.current_bed_id == er_bed_id
        _assert_consistent(db)

    with Session() as db:
        p = _flow(db).transfer_patient(patient_id, icu_id, icu_bed_id)
        assert p.current_status == PatientStatus.TRANSFERRED and p.current_bed_id == icu_bed_id
        assert db.get(BedModel, er_bed_id).status == BedStatus.CLEANING.value
        assert db.get(BedModel, icu_bed_id).current_patient_id == patient_id
        _assert_consistent(db)

    with Session() as db:
        p = _flow(db).discharge_patient(patient_id)
        assert p.current_status == PatientStatus.DISCHARGED and p.current_bed_id is None
        assert db.get(BedModel, icu_bed_id).status == BedStatus.CLEANING.value
        _assert_consistent(db)

    with Session() as db:
        for bed_id in (er_bed_id, icu_bed_id):
            bed = _flow(db).release_bed(bed_id)
            assert bed.status == BedStatus.AVAILABLE and bed.current_patient_id is None
        _assert_consistent(db)
        types = [e.event_type for e in db.query(FlowEventModel).order_by(FlowEventModel.id).all()]
        assert types == [
            "ADMISSION", "TRANSFER", "BED_RELEASE", "DISCHARGE", "BED_RELEASE", "BED_STATUS_CHANGE", "BED_STATUS_CHANGE",
        ]
    engine.dispose()


def test_failed_transfer_leaves_state_untouched(tmp_path):
    engine = build_engine(f"sqlite:///{tmp_path / 'flow2.db'}")
    Base.metadata.create_all(bind=engine)
    Session = sessionmaker(bind=engine, autoflush=False)
    with Session() as db:
        er = DepartmentRepository(db).create(Department(id=None, name="ER", code="ER"))
        b1 = BedRepository(db).create(Bed(id=None, bed_number="1", bed_type=BedType.GENERAL, department_id=er.id))
        b2 = BedRepository(db).create(Bed(id=None, bed_number="2", bed_type=BedType.GENERAL, department_id=er.id))
        p1 = PatientRepository(db).create(Patient(id=None, name="A", age=1, gender="F", medical_record_number="A"))
        p2 = PatientRepository(db).create(Patient(id=None, name="B", age=1, gender="F", medical_record_number="B"))
        db.commit()
        _flow(db).admit_patient(p1.id, er.id, b1.id)
        _flow(db).admit_patient(p2.id, er.id, b2.id)
        events_before = db.query(FlowEventModel).count()
        try:
            _flow(db).transfer_patient(p1.id, er.id, b2.id)  # b2 is occupied -> conflict
            assert False, "expected conflict"
        except Exception as exc:
            assert "cannot be assigned" in str(exc) or "OCCUPIED" in str(exc)
        db.rollback()
    with Session() as db:
        assert db.get(BedModel, b1.id).current_patient_id == p1.id
        assert db.get(BedModel, b1.id).status == BedStatus.OCCUPIED.value
        assert db.get(PatientModel, p1.id).current_bed_id == b1.id
        assert db.query(FlowEventModel).count() == events_before
        _assert_consistent(db)
    engine.dispose()
