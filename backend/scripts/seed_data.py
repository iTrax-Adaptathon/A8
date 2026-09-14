import sys
import os
from datetime import datetime, timezone, timedelta

# Ensure backend directory is in sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app.infrastructure.database import Base, engine, SessionLocal
from app.infrastructure.database.models import (
    DepartmentModel,
    BedModel,
    PatientModel,
    FlowEventModel,
)
from app.domain.enums import PatientStatus, BedStatus, BedType, FlowEventType


def seed_database():
    print("Initializing FlowCare_2 database tables...")
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)

    db = SessionLocal()
    try:
        now = datetime.now(timezone.utc)

        # ----------------------------------------------------
        # 1. DEPARTMENTS
        # ----------------------------------------------------
        print("Seeding departments...")
        depts_data = [
            ("Emergency Department", "EMERGENCY"),
            ("Intensive Care Unit", "ICU"),
            ("General Medicine", "GENMED"),
            ("Cardiology Department", "CARD"),
            ("Pediatrics Ward", "PED"),
            ("Surgical Unit", "SURG"),
        ]

        dept_models = [DepartmentModel(name=name, code=code) for name, code in depts_data]
        db.add_all(dept_models)
        db.commit()

        # Query department IDs map
        dept_map = {d.code: d.id for d in db.query(DepartmentModel).all()}

        # ----------------------------------------------------
        # 2. BEDS (45 Total Beds)
        # ----------------------------------------------------
        print("Seeding beds...")
        beds_data = []

        # Emergency: 8 Beds (EMERGENCY type)
        for i in range(1, 9):
            status = BedStatus.OCCUPIED.value if i <= 5 else BedStatus.AVAILABLE.value
            beds_data.append(BedModel(bed_number=f"ER-{i:02d}", bed_type=BedType.EMERGENCY.value, department_id=dept_map["EMERGENCY"], status=status))

        # ICU: 10 Beds (ICU type)
        for i in range(1, 11):
            status = BedStatus.OCCUPIED.value if i <= 7 else (BedStatus.CLEANING.value if i == 8 else BedStatus.AVAILABLE.value)
            beds_data.append(BedModel(bed_number=f"ICU-{i:02d}", bed_type=BedType.ICU.value, department_id=dept_map["ICU"], status=status))

        # General Medicine: 12 Beds (GENERAL type)
        for i in range(1, 13):
            status = BedStatus.OCCUPIED.value if i <= 8 else BedStatus.AVAILABLE.value
            beds_data.append(BedModel(bed_number=f"GEN-{i:02d}", bed_type=BedType.GENERAL.value, department_id=dept_map["GENMED"], status=status))

        # Cardiology: 6 Beds (GENERAL type)
        for i in range(1, 7):
            status = BedStatus.OCCUPIED.value if i <= 4 else BedStatus.AVAILABLE.value
            beds_data.append(BedModel(bed_number=f"CARD-{i:02d}", bed_type=BedType.GENERAL.value, department_id=dept_map["CARD"], status=status))

        # Pediatrics: 5 Beds (PEDIATRIC type)
        for i in range(1, 6):
            status = BedStatus.OCCUPIED.value if i <= 2 else BedStatus.AVAILABLE.value
            beds_data.append(BedModel(bed_number=f"PED-{i:02d}", bed_type=BedType.PEDIATRIC.value, department_id=dept_map["PED"], status=status))

        # Surgical Unit: 4 Beds (SURGICAL type)
        for i in range(1, 5):
            status = BedStatus.OCCUPIED.value if i <= 2 else BedStatus.AVAILABLE.value
            beds_data.append(BedModel(bed_number=f"SURG-{i:02d}", bed_type=BedType.SURGICAL.value, department_id=dept_map["SURG"], status=status))

        db.add_all(beds_data)
        db.commit()

        bed_map = {b.bed_number: b.id for b in db.query(BedModel).all()}

        # ----------------------------------------------------
        # 3. PATIENTS
        # ----------------------------------------------------
        print("Seeding patients...")
        patients_list = [
            # Admitted to ICU
            PatientModel(
                name="Eleanor Vance",
                age=68,
                gender="Female",
                medical_record_number="MRN-88401",
                current_status=PatientStatus.ADMITTED.value,
                current_department_id=dept_map["ICU"],
                current_bed_id=bed_map["ICU-01"],
                admitted_at=now - timedelta(hours=14),
            ),
            PatientModel(
                name="Arthur Dent",
                age=72,
                gender="Male",
                medical_record_number="MRN-88402",
                current_status=PatientStatus.ADMITTED.value,
                current_department_id=dept_map["ICU"],
                current_bed_id=bed_map["ICU-02"],
                admitted_at=now - timedelta(hours=10),
            ),
            # Transferred from ER to GENMED
            PatientModel(
                name="Sarah Connor",
                age=44,
                gender="Female",
                medical_record_number="MRN-88403",
                current_status=PatientStatus.TRANSFERRED.value,
                current_department_id=dept_map["GENMED"],
                current_bed_id=bed_map["GEN-01"],
                admitted_at=now - timedelta(hours=20),
            ),
            # Admitted to Emergency
            PatientModel(
                name="James Bond",
                age=38,
                gender="Male",
                medical_record_number="MRN-88404",
                current_status=PatientStatus.ADMITTED.value,
                current_department_id=dept_map["EMERGENCY"],
                current_bed_id=bed_map["ER-01"],
                admitted_at=now - timedelta(hours=2),
            ),
            # Registered waiting patient
            PatientModel(
                name="Clara Oswald",
                age=29,
                gender="Female",
                medical_record_number="MRN-88405",
                current_status=PatientStatus.REGISTERED.value,
                current_department_id=None,
                current_bed_id=None,
            ),
            # Discharged patient
            PatientModel(
                name="Bruce Banner",
                age=51,
                gender="Male",
                medical_record_number="MRN-88406",
                current_status=PatientStatus.DISCHARGED.value,
                current_department_id=None,
                current_bed_id=None,
                admitted_at=now - timedelta(days=2),
                discharged_at=now - timedelta(hours=4),
            ),
        ]

        db.add_all(patients_list)
        db.commit()

        # Update bed current_patient_id bindings
        pat_map = {p.medical_record_number: p.id for p in db.query(PatientModel).all()}

        b1 = db.query(BedModel).filter(BedModel.id == bed_map["ICU-01"]).first()
        if b1:
            b1.current_patient_id = pat_map["MRN-88401"]

        b2 = db.query(BedModel).filter(BedModel.id == bed_map["ICU-02"]).first()
        if b2:
            b2.current_patient_id = pat_map["MRN-88402"]

        b3 = db.query(BedModel).filter(BedModel.id == bed_map["GEN-01"]).first()
        if b3:
            b3.current_patient_id = pat_map["MRN-88403"]

        b4 = db.query(BedModel).filter(BedModel.id == bed_map["ER-01"]).first()
        if b4:
            b4.current_patient_id = pat_map["MRN-88404"]

        db.commit()

        # ----------------------------------------------------
        # 4. FLOW EVENTS
        # ----------------------------------------------------
        print("Seeding patient flow events...")
        events = [
            FlowEventModel(
                event_type=FlowEventType.ADMISSION.value,
                patient_id=pat_map["MRN-88401"],
                to_department_id=dept_map["ICU"],
                to_bed_id=bed_map["ICU-01"],
                timestamp=now - timedelta(hours=14),
                notes="Admitted directly to ICU for respiratory monitoring",
            ),
            FlowEventModel(
                event_type=FlowEventType.ADMISSION.value,
                patient_id=pat_map["MRN-88403"],
                to_department_id=dept_map["EMERGENCY"],
                to_bed_id=bed_map["ER-02"],
                timestamp=now - timedelta(hours=20),
                notes="Triage admission in ER",
            ),
            FlowEventModel(
                event_type=FlowEventType.TRANSFER.value,
                patient_id=pat_map["MRN-88403"],
                from_department_id=dept_map["EMERGENCY"],
                to_department_id=dept_map["GENMED"],
                from_bed_id=bed_map["ER-02"],
                to_bed_id=bed_map["GEN-01"],
                timestamp=now - timedelta(hours=12),
                notes="Transferred from ER to General Medicine after stabilization",
            ),
            FlowEventModel(
                event_type=FlowEventType.DISCHARGE.value,
                patient_id=pat_map["MRN-88406"],
                from_department_id=dept_map["GENMED"],
                from_bed_id=bed_map["GEN-02"],
                timestamp=now - timedelta(hours=4),
                notes="Patient successfully discharged following full recovery",
            ),
        ]
        db.add_all(events)
        db.commit()

        print("FlowCare_2 database seed completed successfully!")
    finally:
        db.close()


if __name__ == "__main__":
    seed_database()
