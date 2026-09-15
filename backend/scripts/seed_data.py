"""Deterministic demo data for FlowCare_2.

Run:  python -m scripts.seed_data        (drops and recreates ALL tables)

Everything is derived from a fixed catalogue plus ONE time anchor (the current
hour, UTC), so two runs minutes apart produce the same shape of data.

Consistency rules honoured by the seed:
* every OCCUPIED bed has exactly one current patient, and every patient with a
  non-null current_bed_id points to exactly one OCCUPIED bed;
* REGISTERED / DISCHARGED patients have no bed;
* every BOOKED slot references exactly one SCHEDULED / IN_PROGRESS surgery;
* every ASSIGNED staff member has exactly one ACTIVE assignment;
* every historical event carries an actor and source=SEED.
"""
import json
import sys
import os
from datetime import datetime, timedelta, timezone

# Ensure backend directory is in sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app.infrastructure.database import Base, engine, SessionLocal
from app.infrastructure.database.models import (
    DepartmentModel,
    BedModel,
    PatientModel,
    FlowEventModel,
    TheatreModel,
    TheatreSlotModel,
    SurgeryModel,
    StaffModel,
    StaffAssignmentModel,
    WaitlistEntryModel,
)
from app.domain.enums import (
    PatientStatus,
    BedStatus,
    BedType,
    FlowEventType,
    ResourceType,
    EventSource,
    TheatreStatus,
    TheatreSlotStatus,
    SurgeryStatus,
    StaffRole,
    StaffStatus,
    StaffAssignmentType,
    StaffAssignmentStatus,
    WaitlistResourceType,
    WaitlistStatus,
)

# ---------------------------------------------------------------------------
# Catalogue
# ---------------------------------------------------------------------------
ACTORS = {
    "bedmgr": ("bed-manager-01", "Priya Natarajan"),
    "er": ("nurse-er-04", "Tomás Herrera"),
    "icu": ("charge-nurse-icu", "Grace Okafor"),
    "theatre": ("theatre-coord-02", "Lena Fischer"),
    "system": ("system", "System"),
}

DEPARTMENTS = [
    ("Emergency Department", "EMERGENCY"),
    ("Intensive Care Unit", "ICU"),
    ("General Medicine", "GENMED"),
    ("Cardiology Department", "CARD"),
    ("Pediatrics Ward", "PED"),
    ("Surgical Unit", "SURG"),
]

# (code, prefix, bed_type, count, occupied, cleaning, maintenance)
BED_PLAN = [
    ("EMERGENCY", "ER", BedType.EMERGENCY, 8, 3, 1, 1),
    ("ICU", "ICU", BedType.ICU, 10, 6, 1, 0),
    ("GENMED", "GEN", BedType.GENERAL, 12, 6, 1, 1),
    ("CARD", "CARD", BedType.GENERAL, 6, 4, 0, 0),
    ("PED", "PED", BedType.PEDIATRIC, 5, 2, 0, 0),
    ("SURG", "SURG", BedType.SURGICAL, 4, 2, 1, 0),
]

PATIENT_NAMES = [
    ("Eleanor Vance", 68, "Female"), ("Arthur Dent", 72, "Male"), ("Sarah Connor", 44, "Female"),
    ("James Bond", 38, "Male"), ("Clara Oswald", 29, "Female"), ("Bruce Banner", 51, "Male"),
    ("Amara Diallo", 63, "Female"), ("Hiroshi Tanaka", 57, "Male"), ("Isabela Costa", 34, "Female"),
    ("Noah Lindqvist", 8, "Male"), ("Fatima Al-Sayed", 47, "Female"), ("Dmitri Volkov", 59, "Male"),
    ("Mei-Ling Chen", 71, "Female"), ("Samuel Adeyemi", 42, "Male"), ("Olivia Brennan", 26, "Female"),
    ("Rafael Moreno", 65, "Male"), ("Anika Sharma", 5, "Female"), ("Lucas Petrov", 36, "Male"),
    ("Zainab Hussain", 53, "Female"), ("Kwame Mensah", 61, "Male"), ("Elena Rossi", 49, "Female"),
    ("Jonas Berg", 77, "Male"), ("Aisha Rahman", 31, "Female"), ("Mateo Alvarez", 12, "Male"),
    ("Hannah Schulz", 58, "Female"), ("Omar Haddad", 45, "Male"), ("Yuki Nakamura", 33, "Female"),
    ("Daniel Okoro", 69, "Male"), ("Sofia Marin", 24, "Female"), ("Viktor Novak", 54, "Male"),
    ("Leila Farahani", 39, "Female"), ("Ethan Walsh", 16, "Male"), ("Nadia Kowalski", 62, "Female"),
    ("Carlos Mendes", 48, "Male"),
]


def seed_database():
    print("Initializing FlowCare_2 database tables...")
    with engine.begin() as conn:
        conn.exec_driver_sql("PRAGMA foreign_keys=OFF")
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    with engine.begin() as conn:
        conn.exec_driver_sql("PRAGMA foreign_keys=ON")

    db = SessionLocal()
    try:
        now = datetime.now(timezone.utc).replace(minute=0, second=0, microsecond=0, tzinfo=None)

        def h(hours: float) -> datetime:
            return now + timedelta(hours=hours)

        events = []

        def evt(event_type, actor_key, ts, patient_id=None, resource_type=None, resource_id=None, department_id=None,
                previous_state=None, new_state=None, notes="", metadata=None, from_department_id=None,
                to_department_id=None, from_bed_id=None, to_bed_id=None):
            actor_id, actor_name = ACTORS[actor_key]
            events.append(FlowEventModel(
                event_type=event_type.value, patient_id=patient_id, timestamp=ts, notes=notes,
                resource_type=resource_type.value if resource_type else None, resource_id=resource_id,
                department_id=department_id, previous_state=previous_state, new_state=new_state,
                actor_id=actor_id, actor_name=actor_name, source=EventSource.SEED.value,
                metadata_json=json.dumps(metadata or {}, sort_keys=True),
                from_department_id=from_department_id, to_department_id=to_department_id,
                from_bed_id=from_bed_id, to_bed_id=to_bed_id,
            ))

        # ----------------------------------------------------
        # 1. DEPARTMENTS
        # ----------------------------------------------------
        print("Seeding departments...")
        dept_models = [DepartmentModel(name=name, code=code, created_at=h(-24 * 30)) for name, code in DEPARTMENTS]
        db.add_all(dept_models)
        db.flush()
        dept = {d.code: d for d in dept_models}

        # ----------------------------------------------------
        # 2. BEDS
        # ----------------------------------------------------
        print("Seeding beds...")
        beds = {}
        occupied_beds = []  # in order; patients are attached below
        for code, prefix, bed_type, count, occupied, cleaning, maintenance in BED_PLAN:
            for i in range(1, count + 1):
                if i <= occupied:
                    status = BedStatus.OCCUPIED
                elif i <= occupied + cleaning:
                    status = BedStatus.CLEANING
                elif i <= occupied + cleaning + maintenance:
                    status = BedStatus.MAINTENANCE
                else:
                    status = BedStatus.AVAILABLE
                bed = BedModel(bed_number=f"{prefix}-{i:02d}", bed_type=bed_type.value, department_id=dept[code].id,
                               status=BedStatus.AVAILABLE.value, created_at=h(-24 * 30))
                beds[bed.bed_number] = bed
                bed._target_status = status  # applied once patients exist
                if status == BedStatus.OCCUPIED:
                    occupied_beds.append(bed)
        db.add_all(beds.values())
        db.flush()

        # ----------------------------------------------------
        # 3. PATIENTS
        # ----------------------------------------------------
        print("Seeding patients...")
        patients = []
        for idx, (name, age, gender) in enumerate(PATIENT_NAMES, start=1):
            patients.append(PatientModel(name=name, age=age, gender=gender, medical_record_number=f"MRN-{88400 + idx}",
                                         current_status=PatientStatus.REGISTERED.value, created_at=h(-72 + idx)))
        db.add_all(patients)
        db.flush()

        # 23 occupants: one per OCCUPIED bed. Every 5th occupant arrived via transfer.
        occupants = patients[: len(occupied_beds)]
        for n, (bed, patient) in enumerate(zip(occupied_beds, occupants)):
            admitted_at = h(-(6 + n * 3))
            transferred = n % 5 == 4
            patient.current_department_id = bed.department_id
            patient.current_bed_id = bed.id
            patient.admitted_at = admitted_at
            patient.current_status = (PatientStatus.TRANSFERRED if transferred else PatientStatus.ADMITTED).value
            bed.status = BedStatus.OCCUPIED.value
            bed.current_patient_id = patient.id
            dept_code = next(c for c, d in dept.items() if d.id == bed.department_id)
            actor = "er" if dept_code == "EMERGENCY" else "icu" if dept_code == "ICU" else "bedmgr"
            if transferred:
                er_bed = beds["ER-04"]  # a bed that is now CLEANING: plausible previous location
                evt(FlowEventType.ADMISSION, "er", admitted_at, patient.id, ResourceType.BED, er_bed.id, dept["EMERGENCY"].id,
                    PatientStatus.REGISTERED.value, PatientStatus.ADMITTED.value, "Triage admission in ER",
                    to_department_id=dept["EMERGENCY"].id, to_bed_id=er_bed.id)
                evt(FlowEventType.TRANSFER, actor, admitted_at + timedelta(hours=2), patient.id, ResourceType.BED, bed.id,
                    bed.department_id, PatientStatus.ADMITTED.value, PatientStatus.TRANSFERRED.value,
                    f"Transferred from ER to {dept_code} after stabilisation",
                    from_department_id=dept["EMERGENCY"].id, to_department_id=bed.department_id,
                    from_bed_id=er_bed.id, to_bed_id=bed.id)
                evt(FlowEventType.BED_RELEASE, actor, admitted_at + timedelta(hours=2), patient.id, ResourceType.BED, er_bed.id,
                    dept["EMERGENCY"].id, BedStatus.OCCUPIED.value, BedStatus.CLEANING.value, "Released on transfer",
                    from_bed_id=er_bed.id)
            else:
                notes = "Admitted for observation"
                if n in (0, 1):
                    notes = "Admitted for observation; expected discharge today (discharge-ready)"
                evt(FlowEventType.ADMISSION, actor, admitted_at, patient.id, ResourceType.BED, bed.id, bed.department_id,
                    PatientStatus.REGISTERED.value, PatientStatus.ADMITTED.value, notes,
                    to_department_id=bed.department_id, to_bed_id=bed.id,
                    metadata={"bedPreviousState": "AVAILABLE", "bedNewState": "OCCUPIED"})

        # Remaining bed statuses (CLEANING / MAINTENANCE) with audit trail
        for bed in beds.values():
            target = bed._target_status
            if target == BedStatus.CLEANING:
                bed.status = BedStatus.CLEANING.value
                evt(FlowEventType.BED_STATUS_CHANGE, "bedmgr", h(-1), None, ResourceType.BED, bed.id, bed.department_id,
                    BedStatus.OCCUPIED.value, BedStatus.CLEANING.value, "Awaiting cleaning after discharge")
            elif target == BedStatus.MAINTENANCE:
                bed.status = BedStatus.MAINTENANCE.value
                evt(FlowEventType.BED_STATUS_CHANGE, "bedmgr", h(-30), None, ResourceType.BED, bed.id, bed.department_id,
                    BedStatus.AVAILABLE.value, BedStatus.MAINTENANCE.value, "Bed frame repair")

        # Discharged patients (3) - no bed, full history
        discharged = patients[len(occupants): len(occupants) + 3]
        for n, patient in enumerate(discharged):
            bed = beds["GEN-08"] if n == 0 else beds["ER-04"] if n == 1 else beds["SURG-03"]
            patient.current_status = PatientStatus.DISCHARGED.value
            patient.admitted_at = h(-(48 + n * 12))
            patient.discharged_at = h(-(2 + n * 4))
            evt(FlowEventType.ADMISSION, "bedmgr", patient.admitted_at, patient.id, ResourceType.BED, bed.id, bed.department_id,
                PatientStatus.REGISTERED.value, PatientStatus.ADMITTED.value, "Admitted", to_department_id=bed.department_id, to_bed_id=bed.id)
            evt(FlowEventType.DISCHARGE, "bedmgr", patient.discharged_at, patient.id, ResourceType.PATIENT, patient.id, bed.department_id,
                PatientStatus.ADMITTED.value, PatientStatus.DISCHARGED.value, "Recovered; discharged home",
                from_department_id=bed.department_id, from_bed_id=bed.id)
            evt(FlowEventType.BED_RELEASE, "bedmgr", patient.discharged_at, patient.id, ResourceType.BED, bed.id, bed.department_id,
                BedStatus.OCCUPIED.value, BedStatus.CLEANING.value, "Released on discharge", from_bed_id=bed.id)

        # Waiting (REGISTERED) patients - 4 on the bed queue
        waiting = patients[len(occupants) + 3: len(occupants) + 7]
        db.flush()

        # ----------------------------------------------------
        # 4. THEATRES + SLOTS
        # ----------------------------------------------------
        print("Seeding theatres and slots...")
        theatres = {
            "T1": TheatreModel(name="Theatre 1", department_id=dept["SURG"].id, status=TheatreStatus.AVAILABLE.value, created_at=h(-24 * 30)),
            "T2": TheatreModel(name="Theatre 2", department_id=dept["SURG"].id, status=TheatreStatus.IN_USE.value, created_at=h(-24 * 30)),
            "T3": TheatreModel(name="Theatre 3", department_id=dept["SURG"].id, status=TheatreStatus.CLEANING.value, created_at=h(-24 * 30)),
            "CATH": TheatreModel(name="Cardiac Cath Lab", department_id=dept["CARD"].id, status=TheatreStatus.UNAVAILABLE.value, created_at=h(-24 * 30)),
        }
        db.add_all(theatres.values())
        db.flush()
        evt(FlowEventType.THEATRE_STATUS_CHANGE, "theatre", h(-1), None, ResourceType.THEATRE, theatres["T3"].id, dept["SURG"].id,
            TheatreStatus.IN_USE.value, TheatreStatus.CLEANING.value, "Surgery completed; theatre needs cleaning")
        evt(FlowEventType.THEATRE_STATUS_CHANGE, "theatre", h(-20), None, ResourceType.THEATRE, theatres["CATH"].id, dept["CARD"].id,
            TheatreStatus.AVAILABLE.value, TheatreStatus.UNAVAILABLE.value, "Imaging equipment service")

        def slot(theatre_key, start_hours, duration_hours, status=TheatreSlotStatus.AVAILABLE):
            # BOOKED / COMPLETED slots need their surgery first (CHECK constraint), so
            # they start AVAILABLE and are booked once the surgeries exist.
            initial = status if status == TheatreSlotStatus.CANCELLED else TheatreSlotStatus.AVAILABLE
            s = TheatreSlotModel(theatre_id=theatres[theatre_key].id, start_time=h(start_hours),
                                 end_time=h(start_hours + duration_hours), status=initial.value, created_at=h(-48))
            s._target_status = status
            db.add(s)
            return s

        # Theatre 1: a completed morning case, a booked afternoon case, free evening + tomorrow blocks
        t1_done = slot("T1", -5, 2, TheatreSlotStatus.COMPLETED)
        t1_booked = slot("T1", 3, 3, TheatreSlotStatus.BOOKED)
        t1_free_a = slot("T1", 7, 2)
        t1_free_b = slot("T1", 24 + 1, 3)
        t1_free_c = slot("T1", 24 + 5, 2)
        # Theatre 2: in progress now, booked later today, free tomorrow
        t2_now = slot("T2", -1, 3, TheatreSlotStatus.BOOKED)
        t2_booked = slot("T2", 4, 2, TheatreSlotStatus.BOOKED)
        t2_free = slot("T2", 24 + 2, 4)
        # Theatre 3: cleaning now, free slots later (only matchable once released)
        t3_free_a = slot("T3", 5, 2)
        t3_free_b = slot("T3", 24 + 3, 3)
        # Cath lab: a cancelled slot
        cath_cancelled = slot("CATH", 6, 2, TheatreSlotStatus.CANCELLED)
        db.flush()
        for s in (t1_done, t1_booked, t1_free_a, t1_free_b, t1_free_c, t2_now, t2_booked, t2_free, t3_free_a, t3_free_b):
            evt(FlowEventType.THEATRE_SLOT_CREATED, "theatre", h(-48), None, ResourceType.THEATRE_SLOT, s.id,
                db.get(TheatreModel, s.theatre_id).department_id, None, TheatreSlotStatus.AVAILABLE.value,
                f"Slot {s.start_time.isoformat()} - {s.end_time.isoformat()}", metadata={"theatreId": s.theatre_id})
        evt(FlowEventType.THEATRE_SLOT_CANCELLED, "theatre", h(-20), None, ResourceType.THEATRE_SLOT, cath_cancelled.id,
            dept["CARD"].id, TheatreSlotStatus.AVAILABLE.value, TheatreSlotStatus.CANCELLED.value, "Cath lab unavailable")

        # ----------------------------------------------------
        # 5. STAFF
        # ----------------------------------------------------
        print("Seeding staff...")
        on_shift = (h(-3), h(9))
        night = (h(9), h(21))
        staff_plan = [
            # key, name, role, dept, status, shift
            ("surg1", "Dr. Miranda Bailey", StaffRole.SURGEON, "SURG", StaffStatus.ASSIGNED, on_shift),
            ("surg2", "Dr. Derek Shepherd", StaffRole.SURGEON, "SURG", StaffStatus.ASSIGNED, on_shift),
            ("surg3", "Dr. Cristina Yang", StaffRole.SURGEON, "SURG", StaffStatus.AVAILABLE, on_shift),
            ("surg4", "Dr. Preston Burke", StaffRole.SURGEON, "SURG", StaffStatus.OFF_DUTY, night),
            ("anae1", "Dr. Ben Warren", StaffRole.ANAESTHETIST, "SURG", StaffStatus.ASSIGNED, on_shift),
            ("anae2", "Dr. Amelia Chen", StaffRole.ANAESTHETIST, "SURG", StaffStatus.OFF_DUTY, night),
            ("nurse_s1", "Bokhee An", StaffRole.NURSE, "SURG", StaffStatus.AVAILABLE, on_shift),
            ("nurse_s2", "Olivia Harper", StaffRole.NURSE, "SURG", StaffStatus.ASSIGNED, on_shift),
            ("doc_icu", "Dr. Richard Webber", StaffRole.DOCTOR, "ICU", StaffStatus.AVAILABLE, on_shift),
            ("nurse_icu1", "Grace Okafor", StaffRole.NURSE, "ICU", StaffStatus.ASSIGNED, on_shift),
            ("nurse_icu2", "Tunde Bakare", StaffRole.NURSE, "ICU", StaffStatus.AVAILABLE, on_shift),
            ("nurse_icu3", "Marta Silva", StaffRole.NURSE, "ICU", StaffStatus.OFF_DUTY, night),
            ("doc_er", "Dr. Owen Hunt", StaffRole.DOCTOR, "EMERGENCY", StaffStatus.AVAILABLE, on_shift),
            ("nurse_er1", "Tomás Herrera", StaffRole.NURSE, "EMERGENCY", StaffStatus.ASSIGNED, on_shift),
            ("nurse_er2", "Ada Nwosu", StaffRole.NURSE, "EMERGENCY", StaffStatus.AVAILABLE, on_shift),
            ("porter_er", "Sam Whitfield", StaffRole.PORTER, "EMERGENCY", StaffStatus.AVAILABLE, on_shift),
            ("doc_gen", "Dr. April Kepner", StaffRole.DOCTOR, "GENMED", StaffStatus.AVAILABLE, on_shift),
            ("nurse_gen1", "Ifeoma Eze", StaffRole.NURSE, "GENMED", StaffStatus.AVAILABLE, on_shift),
            ("nurse_gen2", "Jonah Reyes", StaffRole.NURSE, "GENMED", StaffStatus.OFF_DUTY, night),
            ("doc_card", "Dr. Maggie Pierce", StaffRole.DOCTOR, "CARD", StaffStatus.AVAILABLE, on_shift),
            ("nurse_card", "Helen Park", StaffRole.NURSE, "CARD", StaffStatus.OFF_DUTY, night),
            ("doc_ped", "Dr. Alex Karev", StaffRole.DOCTOR, "PED", StaffStatus.AVAILABLE, on_shift),
            ("nurse_ped", "Rosa Delgado", StaffRole.NURSE, "PED", StaffStatus.AVAILABLE, on_shift),
        ]
        staff = {}
        for key, name, role, code, status, (start, end) in staff_plan:
            staff[key] = StaffModel(name=name, role=role.value, department_id=dept[code].id, shift_start=start, shift_end=end,
                                    status=StaffStatus.AVAILABLE.value, created_at=h(-24 * 30))
        db.add_all(staff.values())
        db.flush()
        for key, name, role, code, status, _ in staff_plan:
            if status == StaffStatus.OFF_DUTY:
                staff[key].status = StaffStatus.OFF_DUTY.value
                evt(FlowEventType.STAFF_STATUS_CHANGE, "system", h(-3), None, ResourceType.STAFF, staff[key].id, dept[code].id,
                    StaffStatus.AVAILABLE.value, StaffStatus.OFF_DUTY.value, "Shift ended")

        # ----------------------------------------------------
        # 6. SURGERIES (+ theatre queue) and staff assignments
        # ----------------------------------------------------
        print("Seeding surgeries...")
        surg_patients = {  # use admitted patients of the surgical / cardiology / genmed beds
            "done": occupants[21],       # SURG-01 occupant
            "in_progress": occupants[22],  # SURG-02 occupant
            "sched1": occupants[15],     # CARD occupant -> surgical procedure
            "sched2": occupants[12],     # GENMED occupant
            "wait1": occupants[13],
            "wait2": occupants[14],
            "wait3": occupants[16],
            "cancelled": discharged[2],
        }

        def surgery(key, name, minutes, priority, status, role=None, theatre_key=None, slot_obj=None, created=-30,
                    scheduled=None, started=None, completed=None):
            p = surg_patients[key]
            s = SurgeryModel(patient_id=p.id, department_id=dept["SURG"].id, procedure_name=name, duration_minutes=minutes,
                             priority=priority, status=status.value,
                             theatre_id=theatres[theatre_key].id if theatre_key else None,
                             slot_id=slot_obj.id if slot_obj else None,
                             required_staff_role=role.value if role else None, created_at=h(created),
                             scheduled_at=h(scheduled) if scheduled is not None else None,
                             started_at=h(started) if started is not None else None,
                             completed_at=h(completed) if completed is not None else None)
            db.add(s)
            db.flush()
            evt(FlowEventType.SURGERY_CREATED, "theatre", h(created), p.id, ResourceType.SURGERY, s.id, dept["SURG"].id,
                None, SurgeryStatus.WAITING.value, f"Surgery '{name}' created (priority {priority})",
                metadata={"durationMinutes": minutes})
            return s

        s_done = surgery("done", "Laparoscopic cholecystectomy", 90, 2, SurgeryStatus.COMPLETED, StaffRole.SURGEON, "T1", t1_done,
                         created=-40, scheduled=-30, started=-5, completed=-3.5)
        t1_done.status = t1_done._target_status.value
        t1_done.surgery_id = s_done.id
        s_prog = surgery("in_progress", "Open reduction internal fixation", 150, 1, SurgeryStatus.IN_PROGRESS, StaffRole.SURGEON, "T2", t2_now,
                         created=-26, scheduled=-20, started=-1)
        t2_now.status = t2_now._target_status.value
        t2_now.surgery_id = s_prog.id
        s_sched1 = surgery("sched1", "Coronary artery bypass graft", 180, 1, SurgeryStatus.SCHEDULED, StaffRole.SURGEON, "T1", t1_booked,
                           created=-28, scheduled=-10)
        t1_booked.status = t1_booked._target_status.value
        t1_booked.surgery_id = s_sched1.id
        s_sched2 = surgery("sched2", "Inguinal hernia repair", 90, 3, SurgeryStatus.SCHEDULED, StaffRole.SURGEON, "T2", t2_booked,
                           created=-22, scheduled=-8)
        t2_booked.status = t2_booked._target_status.value
        t2_booked.surgery_id = s_sched2.id
        s_wait1 = surgery("wait1", "Appendectomy", 60, 1, SurgeryStatus.WAITING, StaffRole.SURGEON, created=-6)
        s_wait2 = surgery("wait2", "Total knee replacement", 150, 3, SurgeryStatus.WAITING, StaffRole.SURGEON, created=-12)
        s_wait3 = surgery("wait3", "Carpal tunnel release", 45, 4, SurgeryStatus.WAITING, None, created=-9)
        s_cancel = surgery("cancelled", "Tonsillectomy", 45, 4, SurgeryStatus.CANCELLED, None, created=-60)
        db.flush()

        for s, sl, th in ((s_done, t1_done, "T1"), (s_prog, t2_now, "T2"), (s_sched1, t1_booked, "T1"), (s_sched2, t2_booked, "T2")):
            evt(FlowEventType.SURGERY_SCHEDULED, "theatre", s.scheduled_at, s.patient_id, ResourceType.SURGERY, s.id, dept["SURG"].id,
                SurgeryStatus.WAITING.value, SurgeryStatus.SCHEDULED.value, f"Scheduled in {theatres[th].name}",
                metadata={"theatreId": theatres[th].id, "slotId": sl.id})
            evt(FlowEventType.THEATRE_SLOT_BOOKED, "theatre", s.scheduled_at, s.patient_id, ResourceType.THEATRE_SLOT, sl.id, dept["SURG"].id,
                TheatreSlotStatus.AVAILABLE.value, TheatreSlotStatus.BOOKED.value, f"Booked by surgery {s.id}",
                metadata={"theatreId": theatres[th].id, "surgeryId": s.id})
        for s in (s_done, s_prog):
            evt(FlowEventType.SURGERY_STARTED, "theatre", s.started_at, s.patient_id, ResourceType.SURGERY, s.id, dept["SURG"].id,
                SurgeryStatus.SCHEDULED.value, SurgeryStatus.IN_PROGRESS.value, "Surgery started")
        evt(FlowEventType.THEATRE_STATUS_CHANGE, "theatre", s_prog.started_at, s_prog.patient_id, ResourceType.THEATRE, theatres["T2"].id,
            dept["SURG"].id, TheatreStatus.AVAILABLE.value, TheatreStatus.IN_USE.value, f"Surgery {s_prog.id} started")
        evt(FlowEventType.SURGERY_COMPLETED, "theatre", s_done.completed_at, s_done.patient_id, ResourceType.SURGERY, s_done.id,
            dept["SURG"].id, SurgeryStatus.IN_PROGRESS.value, SurgeryStatus.COMPLETED.value, "Surgery completed")
        evt(FlowEventType.THEATRE_SLOT_COMPLETED, "theatre", s_done.completed_at, s_done.patient_id, ResourceType.THEATRE_SLOT, t1_done.id,
            dept["SURG"].id, TheatreSlotStatus.BOOKED.value, TheatreSlotStatus.COMPLETED.value, f"Surgery {s_done.id} completed")
        evt(FlowEventType.SURGERY_CANCELLED, "theatre", h(-50), s_cancel.patient_id, ResourceType.SURGERY, s_cancel.id, dept["SURG"].id,
            SurgeryStatus.WAITING.value, SurgeryStatus.CANCELLED.value, "Patient declined procedure")

        # Staff assignments (ACTIVE -> staff ASSIGNED; released ones for history)
        print("Seeding staff assignments...")

        def assign(staff_key, a_type, surgery_obj=None, patient_obj=None, start=None, end=None, status=StaffAssignmentStatus.ACTIVE,
                   released=None, ts=-2):
            st = staff[staff_key]
            dept_id = surgery_obj.department_id if surgery_obj else patient_obj.current_department_id
            a = StaffAssignmentModel(staff_id=st.id, assignment_type=a_type.value, surgery_id=surgery_obj.id if surgery_obj else None,
                                     patient_id=patient_obj.id if patient_obj else None, department_id=dept_id,
                                     start_time=start or h(ts), end_time=end, status=status.value,
                                     released_at=h(released) if released is not None else None)
            db.add(a)
            db.flush()
            pid = surgery_obj.patient_id if surgery_obj else patient_obj.id
            evt(FlowEventType.STAFF_ASSIGNED, "theatre" if surgery_obj else "bedmgr", h(ts), pid, ResourceType.STAFF, st.id, dept_id,
                StaffStatus.AVAILABLE.value, StaffStatus.ASSIGNED.value, f"{st.name} assigned to {a_type.value.lower()}",
                metadata={"assignmentId": a.id, "surgeryId": a.surgery_id, "patientId": a.patient_id})
            if status == StaffAssignmentStatus.ACTIVE:
                st.status = StaffStatus.ASSIGNED.value
            else:
                evt(FlowEventType.STAFF_RELEASED, "system", h(released), pid, ResourceType.STAFF, st.id, dept_id,
                    StaffStatus.ASSIGNED.value, StaffStatus.AVAILABLE.value, "Released", metadata={"assignmentId": a.id})
            return a

        assign("surg1", StaffAssignmentType.SURGERY, surgery_obj=s_prog, start=t2_now.start_time, end=t2_now.end_time, ts=-1.5)
        assign("anae1", StaffAssignmentType.SURGERY, surgery_obj=s_prog, start=t2_now.start_time, end=t2_now.end_time, ts=-1.5)
        assign("nurse_s2", StaffAssignmentType.SURGERY, surgery_obj=s_prog, start=t2_now.start_time, end=t2_now.end_time, ts=-1.5)
        assign("surg2", StaffAssignmentType.SURGERY, surgery_obj=s_sched1, start=t1_booked.start_time, end=t1_booked.end_time, ts=-2)
        assign("nurse_icu1", StaffAssignmentType.PATIENT, patient_obj=occupants[3], ts=-2.5)
        assign("nurse_er1", StaffAssignmentType.PATIENT, patient_obj=occupants[0], ts=-3)
        # historical, released assignment for the completed surgery
        assign("surg3", StaffAssignmentType.SURGERY, surgery_obj=s_done, start=t1_done.start_time, end=t1_done.end_time,
               status=StaffAssignmentStatus.RELEASED, released=-3.5, ts=-5.5)

        # ----------------------------------------------------
        # 7. WAITLIST
        # ----------------------------------------------------
        print("Seeding waitlist...")
        entries = []

        def wait(patient_obj, rtype, code, priority, requested, reason, surgery_obj=None, bed_type=None, role=None,
                 status=WaitlistStatus.WAITING, fulfilled=None, fulfilled_resource_id=None):
            e = WaitlistEntryModel(patient_id=patient_obj.id, resource_type=rtype.value, department_id=dept[code].id, priority=priority,
                                   requested_at=h(requested), status=status.value, reason=reason,
                                   surgery_id=surgery_obj.id if surgery_obj else None,
                                   required_bed_type=bed_type.value if bed_type else None,
                                   required_staff_role=role.value if role else None,
                                   fulfilled_at=h(fulfilled) if fulfilled is not None else None,
                                   fulfilled_resource_id=fulfilled_resource_id)
            db.add(e)
            db.flush()
            evt(FlowEventType.WAITLIST_ADDED, "bedmgr" if rtype != WaitlistResourceType.THEATRE else "theatre", h(requested),
                patient_obj.id, ResourceType.WAITLIST_ENTRY, e.id, dept[code].id, None, WaitlistStatus.WAITING.value, reason,
                metadata={"resourceType": rtype.value, "priority": priority})
            if status == WaitlistStatus.FULFILLED:
                evt(FlowEventType.WAITLIST_FULFILLED, "system", h(fulfilled), patient_obj.id, ResourceType.WAITLIST_ENTRY, e.id,
                    dept[code].id, WaitlistStatus.WAITING.value, WaitlistStatus.FULFILLED.value, "Resource assigned")
            elif status == WaitlistStatus.CANCELLED:
                evt(FlowEventType.WAITLIST_REMOVED, "bedmgr", h(fulfilled or requested + 1), patient_obj.id, ResourceType.WAITLIST_ENTRY, e.id,
                    dept[code].id, WaitlistStatus.WAITING.value, WaitlistStatus.CANCELLED.value, "Request withdrawn")
            entries.append(e)
            return e

        # Bed queue: 4 REGISTERED patients; two share priority 2 so the longest wait breaks the tie
        wait(waiting[0], WaitlistResourceType.BED, "ICU", 1, -1.5, "Post-resus; needs ICU bed", bed_type=BedType.ICU)
        wait(waiting[1], WaitlistResourceType.BED, "GENMED", 2, -4, "Pneumonia; awaiting medical bed")
        wait(waiting[2], WaitlistResourceType.BED, "GENMED", 2, -2, "Cellulitis; awaiting medical bed")
        wait(waiting[3], WaitlistResourceType.BED, "PED", 3, -0.5, "Asthma exacerbation; awaiting paediatric bed")
        # Theatre queue: one entry per WAITING surgery
        wait(surg_patients["wait1"], WaitlistResourceType.THEATRE, "SURG", 1, -6, "Theatre slot for Appendectomy", surgery_obj=s_wait1)
        wait(surg_patients["wait2"], WaitlistResourceType.THEATRE, "SURG", 3, -12, "Theatre slot for Total knee replacement", surgery_obj=s_wait2)
        wait(surg_patients["wait3"], WaitlistResourceType.THEATRE, "SURG", 4, -9, "Theatre slot for Carpal tunnel release", surgery_obj=s_wait3)
        # Staff queue
        wait(occupants[4], WaitlistResourceType.STAFF, "ICU", 2, -1, "Needs 1:1 nursing", role=StaffRole.NURSE)
        wait(surg_patients["sched1"], WaitlistResourceType.STAFF, "SURG", 1, -8, "Anaesthetist for CABG", surgery_obj=s_sched1, role=StaffRole.ANAESTHETIST)
        # History: fulfilled / cancelled entries
        wait(occupants[2], WaitlistResourceType.BED, "ICU", 1, -14, "Needs ICU bed", status=WaitlistStatus.FULFILLED, fulfilled=-12,
             fulfilled_resource_id=occupied_beds[2].id)
        wait(discharged[0], WaitlistResourceType.BED, "GENMED", 3, -50, "Awaiting medical bed", status=WaitlistStatus.FULFILLED, fulfilled=-48,
             fulfilled_resource_id=beds["GEN-08"].id)
        wait(discharged[1], WaitlistResourceType.STAFF, "EMERGENCY", 3, -40, "Porter for transfer", role=StaffRole.PORTER,
             status=WaitlistStatus.CANCELLED, fulfilled=-39)

        # A recorded auto-match example for the fulfilled ICU entry
        evt(FlowEventType.MATCH_IDENTIFIED, "system", h(-12), occupants[2].id, ResourceType.BED, occupied_beds[2].id, dept["ICU"].id,
            None, None, "Compatible Intensive Care Unit ICU bed; priority 1; longest waiting eligible patient.",
            metadata={"waitlistEntryId": entries[-3].id, "rank": 1})
        for e in events:
            if e.event_type == FlowEventType.MATCH_IDENTIFIED.value:
                e.source = EventSource.AUTO_MATCH.value

        db.add_all(events)
        db.commit()

        print("FlowCare_2 database seed completed successfully!")
        print(f"  departments={len(dept)} beds={len(beds)} patients={len(patients)} theatres={len(theatres)} "
              f"staff={len(staff)} waitlist={len(entries)} events={len(events)}")
    finally:
        db.close()


if __name__ == "__main__":
    seed_database()
