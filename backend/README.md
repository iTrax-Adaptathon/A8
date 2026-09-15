# FlowCare_2 Backend — Hospital Capacity, Patient Flow & Resource Orchestration

FastAPI + SQLAlchemy 2 + SQLite backend for the Adaptathon FlowCare platform. It gives a
hospital live visibility of **beds, theatres and theatre slots, staff, waiting patients and
surgeries**, and orchestrates **deterministic matching and validated assignments** with a
complete, immutable audit trail and realtime updates for the separately built React frontend.

> **This system contains no LLM, RAG, machine learning or AI-based operational
> decision-making. All decisions use deterministic predefined business rules.**
> Every prioritisation, match, capacity figure and state transition is an explicit rule in
> `app/domain/policies.py` or a plain database query.

---

## 1. Inherited functionality (kept and hardened)

The backend was supplied with Department / Bed / Patient / FlowEvent, admission, transfer,
discharge and a bed-only capacity endpoint. All of that still exists at the same paths.
Integrity problems found during inspection and fixed:

| Problem | Fix |
|---|---|
| `PATCH /beds/{id}/status` could set an OCCUPIED bed to AVAILABLE, leaving the patient pointing at it | Manual status changes go through `BedPolicy`; OCCUPIED beds only leave that state via transfer/discharge (→ CLEANING) |
| Beds could be created OCCUPIED without a patient | Rejected (422); CHECK constraint `(status='OCCUPIED') = (current_patient_id IS NOT NULL)` |
| Discharge set the bed straight to AVAILABLE | Discharge/transfer release to **CLEANING**; `POST /beds/{id}/release` moves CLEANING → AVAILABLE |
| Capacity counted CLEANING/MAINTENANCE beds as available (`total - occupied`) | `available` = COUNT of active beds in status AVAILABLE |
| `Department.beds` had `cascade="all, delete-orphan"` | Removed; departments/beds/theatres/staff are **deactivated** (`isActive=false`), never deleted; history survives |
| Each repository call committed separately (admission = 3 transactions) and used check-then-act | One transaction per workflow; **atomic compare-and-set UPDATEs**; unique partial indexes; failed operations roll back completely |
| SQLAlchemy warning: FK cycle `beds ↔ patients` | `use_alter=True` on `patients.current_bed_id` (tests run with `-W error::SAWarning`) |
| All domain errors returned 400 | 404 / 409 / 422 (see §11) |
| SQLite foreign keys not enforced; CORS hardcoded `*` | `PRAGMA foreign_keys=ON`, WAL, busy timeout; `CORS_ORIGINS` env setting |
| Seed had OCCUPIED beds with no patient | Rewritten deterministic seed with consistent links |

## 2. Added functionality

* **Theatres + TheatreSlots** (no overlap, 15 min–24 h, independent statuses)
* **Surgeries** (WAITING → SCHEDULED → IN_PROGRESS → COMPLETED / CANCELLED, required staff role)
* **Staff + StaffAssignments** (role / department / shift / one-active-assignment rules)
* **Waitlist** — single deterministic queue for BED, THEATRE and STAFF requests
* **Matching** — read-only candidate computation + confirmation through the standard workflows, and automatic assignment after a resource becomes AVAILABLE
* **Audit trail** with actor tracking, previous/new state and source; `GET /patients/{id}/history`
* **Capacity** snapshot for beds, theatres, staff, queues and per-department occupancy
* **Realtime** WebSocket `/api/v1/ws/capacity` (emitted strictly after commit)
* Soft delete, pagination (`limit`/`offset` + `X-Total-Count`), camelCase JSON, OpenAPI docs

## 3. Architecture

```
app/
  api/routes/        FastAPI routers (thin: parse → service → schema)
  api/schemas/       Pydantic request/response models (CamelModel base)
  api/pagination.py  limit/offset + X-Total-Count helper
  application/       services: bed, patient, department, theatre, surgery, staff, waitlist,
                     matching, capacity, audit (TransactionalService base)
  orchestration/     flow_orchestration_service (admit/transfer/discharge/release_bed)
                     release_orchestration_service (release → auto-match chain)
  domain/            entities (dataclasses), enums, policies (all business rules)
  infrastructure/    SQLAlchemy models, session/engine, repositories (flush-only, atomic claims)
  realtime/          EventBus + WebSocket ConnectionManager
  core/              settings, dependency wiring, actor header dependency, exception handlers
scripts/seed_data.py deterministic demo data
tests/               pytest suite (81 tests)
```

Request flow: `route → service.method(...) → with self.transaction(): validate → mutate via repositories → audit.record() → commit → event_bus.publish()`.

Repositories never commit. `TransactionalService.transaction()` commits once, translates
`IntegrityError` into 409, rolls back on any exception and only *then* publishes realtime events.

## 4. Database entities (SQLite `flowcare_2.db`)

| Table | Key columns / constraints |
|---|---|
| `departments` | name, code (unique), is_active |
| `beds` | bed_number (unique), bed_type, department_id, status, current_patient_id, is_active. CHECK occupied⇔patient; unique partial index on `current_patient_id` |
| `patients` | medical_record_number (unique), current_status, current_department_id, current_bed_id (unique partial index), admitted_at, discharged_at |
| `flow_events` | append-only audit log: event_type, timestamp, patient_id, resource_type/id, department_id, previous_state, new_state, actor_id, actor_name, source, metadata_json (+ inherited from/to department/bed) |
| `theatres` | name (unique), department_id, status, is_active |
| `theatre_slots` | theatre_id, start_time, end_time, status, surgery_id. CHECK booked/completed⇔surgery; unique partial index one BOOKED slot per surgery |
| `surgeries` | patient_id, department_id, procedure_name, duration_minutes (15–1440), priority (1–5), status, theatre_id, slot_id, required_staff_role, timestamps |
| `staff` | name, role, department_id, shift_start, shift_end, status, is_active |
| `staff_assignments` | staff_id, assignment_type (SURGERY/PATIENT), surgery_id/patient_id, department_id, start/end, status. Unique partial index: one ACTIVE per staff |
| `waitlist_entries` | patient_id, resource_type, department_id, priority, requested_at, status, reason, surgery_id, required_bed_type, required_staff_role, fulfilled_at/resource |

All datetimes are stored as naive UTC and serialised with a trailing `Z`; requests may send any ISO-8601 offset.

## 5. Resource states and transitions

**Bed** `AVAILABLE | OCCUPIED | CLEANING | MAINTENANCE`
* admit/transfer: AVAILABLE → OCCUPIED (atomic claim)
* transfer/discharge: OCCUPIED → CLEANING (never straight to AVAILABLE)
* `POST /beds/{id}/release`: CLEANING → AVAILABLE, then matching
* `PATCH /beds/{id}/status`: AVAILABLE↔CLEANING↔MAINTENANCE↔AVAILABLE only; OCCUPIED beds → 409; setting OCCUPIED → 409

**Theatre** `AVAILABLE | IN_USE | CLEANING | UNAVAILABLE` — surgery start: AVAILABLE → IN_USE; surgery complete: IN_USE → CLEANING; `POST /theatres/{id}/release`: CLEANING → AVAILABLE; manual: AVAILABLE→UNAVAILABLE|CLEANING, CLEANING→AVAILABLE|UNAVAILABLE, UNAVAILABLE→AVAILABLE.

**TheatreSlot** `AVAILABLE | BOOKED | COMPLETED | CANCELLED` — independent of the theatre status. Scheduling: AVAILABLE → BOOKED (atomic, one surgery); unschedule/cancel surgery: BOOKED → AVAILABLE; complete: BOOKED → COMPLETED; `POST /theatre-slots/{id}/cancel`: AVAILABLE → CANCELLED. Overlapping live slots in the same theatre are rejected (409).

**Surgery** `WAITING → SCHEDULED → IN_PROGRESS → COMPLETED`, `WAITING|SCHEDULED → CANCELLED`, `SCHEDULED → WAITING` (unschedule). Scheduling requires: patient not discharged, theatre active **and** AVAILABLE, slot AVAILABLE, same department, slot length ≥ duration. Start requires theatre AVAILABLE and (if `requiredStaffRole` set) an ACTIVE assignment with that role.

**Staff** `AVAILABLE | ASSIGNED | OFF_DUTY` — `shiftStart`/`shiftEnd` are the working hours. assign: AVAILABLE → ASSIGNED (atomic); release: ASSIGNED → AVAILABLE; manual: AVAILABLE ↔ OFF_DUTY. Assignment requires role match, department match, window inside shift, no other ACTIVE assignment.

**Patient** `REGISTERED → ADMITTED → TRANSFERRED* → DISCHARGED` (terminal). Discharged patients cannot transfer, be re-admitted, get surgeries or waitlist entries.

**Waitlist entry** `WAITING → FULFILLED | CANCELLED` (rows are never deleted).

## 6. Patient flow rules

* A patient holds at most one bed; a bed holds at most one patient (DB-enforced).
* Bed must belong to the target department and be active + AVAILABLE.
* Admission fulfils the patient's WAITING bed request for that department; discharge cancels the patient's open bed requests.
* A failed workflow leaves no partial writes (single transaction, rollback on any error).

## 7. Queue rule (`WaitlistPolicy`)

```
ORDER BY priority ASC (1 = most urgent … 5),
         requested_at ASC (longest waiting first),
         id ASC (total order)
```
`GET /waitlist` always returns this order. **The frontend must not re-sort.**
Creating a surgery automatically adds a THEATRE entry (`surgeryId` set); BED and STAFF entries are added via `POST /waitlist`.

## 8. Matching rule (`MatchingPolicy`, `MatchingService`)

`GET /matches?resourceType=&resourceId=` is **read-only**: it walks the WAITING queue of the resource's department in queue order and keeps only eligible entries. It never writes.

| Resource | Eligibility (all must hold) |
|---|---|
| BED | bed active, AVAILABLE, empty; `departmentId` equal; `requiredBedType` (if set) equal; patient not DISCHARGED; REGISTERED patient has no bed; patient not already in this bed |
| THEATRE_SLOT | slot AVAILABLE and in the future; parent theatre active **and** AVAILABLE; theatre department = surgery department; surgery WAITING with no slot; slot length ≥ `durationMinutes`; patient not DISCHARGED |
| STAFF | staff active, AVAILABLE, no ACTIVE assignment; role = `requiredStaffRole`; department equal; shift covers the window (surgery slot window or now); patient not DISCHARGED |

Each candidate carries a reason, e.g. `Compatible Cardiology GENERAL bed; priority 3; longest waiting eligible patient.`

**MATCH IDENTIFIED ≠ ASSIGNMENT CONFIRMED.** `POST /matches/confirm` records `MATCH_IDENTIFIED` and then runs *exactly* the manual workflow (`admit_patient`/`transfer_patient`, `schedule_surgery`, `assign_staff`). A rejected confirmation is rolled back and stored as `ASSIGNMENT_REJECTED` (409).

**Automatic matching** runs when a resource becomes AVAILABLE (bed release, bed/theatre/staff status → AVAILABLE, theatre release → only its slots that are already AVAILABLE, slot created, surgery unscheduled/cancelled → freed slot, surgery completed/cancelled → released staff, assignment released). It is enabled by `AUTO_ASSIGN_ON_RELEASE=true` and can be overridden per request with `autoAssign`. The release commits first; each auto-assignment attempt is its own transaction, so a rejected attempt never undoes the release. Responses of release/action endpoints include the `autoAssignment(s)` outcome.

## 9. Audit trail and actor tracking

Every state-changing operation appends one or more `flow_events` rows (never updated/deleted):
`ADMISSION, TRANSFER, DISCHARGE, BED_RELEASE, BED_STATUS_CHANGE, RESOURCE_CREATED, RESOURCE_DEACTIVATED, THEATRE_STATUS_CHANGE, THEATRE_SLOT_CREATED/BOOKED/RELEASED/CANCELLED/COMPLETED, SURGERY_CREATED/SCHEDULED/UNSCHEDULED/STARTED/COMPLETED/CANCELLED, STAFF_STATUS_CHANGE, STAFF_ASSIGNED, STAFF_RELEASED, WAITLIST_ADDED/REMOVED/FULFILLED, MATCH_IDENTIFIED, ASSIGNMENT_REJECTED`.

Each row has `timestamp, eventType, patientId, resourceType, resourceId, departmentId, previousState, newState, actorId, actorName, source (MANUAL | AUTO_MATCH | SYSTEM | SEED), notes, metadata`.

Actor: send `X-Actor-ID` and `X-Actor-Name` headers on any request. Defaults: `system` / `System`. No authentication.
`GET /patients/{id}/history` returns the complete chronological (oldest first) timeline; `GET /flow-events` is the global log (newest first) with filters.

## 10. Realtime WebSocket

`ws://<host>/api/v1/ws/capacity` — one JSON message per committed change:

```json
{"type": "BED_UPDATED", "resourceType": "BED", "resourceId": 12, "patientId": 5, "departmentId": 2,
 "previousState": "CLEANING", "newState": "AVAILABLE", "actorId": "nurse-7", "source": "MANUAL",
 "timestamp": "2026-09-15T10:00:00+00:00"}
```
Types: `PATIENT_UPDATED, BED_UPDATED, DEPARTMENT_UPDATED, THEATRE_UPDATED, THEATRE_SLOT_UPDATED, SURGERY_UPDATED, STAFF_UPDATED, WAITLIST_UPDATED, MATCH_ASSIGNED`.
Order of every mutation: **validate → mutate → commit → broadcast**. Failed/rolled-back operations emit nothing; delivery problems are logged and never affect the database. `GET /api/v1/realtime` documents the contract. On receipt the frontend should re-fetch `/capacity` and/or the affected resource.

## 11. API

Base path `/api/v1`. Swagger UI `/docs`, ReDoc `/redoc`, spec `/api/v1/openapi.json`.
Conventions: camelCase responses; requests accept camelCase and snake_case; list endpoints return bare arrays with `?limit=` (1–500, default 100) `&offset=` and the `X-Total-Count` header; deterministic ordering everywhere.
Errors: `404 {"error":"NOT_FOUND"}`, `409 {"error":"CONFLICT"}` (invalid transition, double booking, lost concurrent claim, DB constraint), `422 {"error":"DOMAIN_VALIDATION_ERROR"}` or FastAPI `{"detail":[...]}` for schema errors.

| Group | Endpoints |
|---|---|
| Patients | `GET/POST /patients`, `GET /patients/{id}`, `GET /patients/{id}/history`, `POST /patients/{id}/admit\|transfer\|discharge` |
| Beds | `GET/POST /beds`, `GET /beds/available`, `GET /beds/{id}`, `PATCH /beds/{id}/status`, `POST /beds/{id}/release`, `DELETE /beds/{id}` (deactivate) |
| Departments | `GET/POST /departments`, `GET /departments/{id}`, `DELETE /departments/{id}` (deactivate) |
| Capacity | `GET /capacity` |
| Flow events / audit | `GET /flow-events?patientId&resourceType&resourceId&eventType&departmentId` |
| Theatres | `GET/POST /theatres`, `GET /theatres/{id}`, `PATCH /theatres/{id}/status`, `POST /theatres/{id}/release`, `DELETE /theatres/{id}` |
| Theatre slots | `GET/POST /theatre-slots`, `GET /theatre-slots/{id}`, `POST /theatre-slots/{id}/cancel` |
| Surgeries | `GET/POST /surgeries`, `GET /surgeries/{id}`, `POST /surgeries/{id}/schedule\|unschedule\|start\|complete\|cancel` |
| Staff | `GET/POST /staff`, `GET /staff/{id}`, `PATCH /staff/{id}/status`, `POST /staff/{id}/assign`, `DELETE /staff/{id}`, `GET /staff-assignments`, `GET /staff-assignments/{id}`, `POST /staff-assignments/{id}/release` |
| Waitlist | `GET/POST /waitlist`, `GET /waitlist/{id}`, `DELETE /waitlist/{id}` (→ CANCELLED) |
| Matches | `GET /matches?resourceType=BED\|THEATRE_SLOT\|STAFF&resourceId=`, `POST /matches/confirm` |
| Realtime | `GET /realtime`, `WS /ws/capacity` |

## 12. Setup

```bash
cd backend
python -m venv .venv && .venv\Scripts\activate      # (Linux/macOS: source .venv/bin/activate)
pip install -r requirements.txt
python -m scripts.seed_data                          # creates/reset flowcare_2.db with demo data
uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload
```
Python 3.11+ (developed on 3.14). No additional services are required.

Environment variables (optional, also read from `backend/.env`):

| Variable | Default | Purpose |
|---|---|---|
| `DATABASE_URL` | `sqlite:///./flowcare_2.db` | SQLAlchemy URL |
| `CORS_ORIGINS` | `http://localhost:5173,http://127.0.0.1:5173,http://localhost:3000,http://127.0.0.1:3000` | comma-separated frontend origins |
| `AUTO_ASSIGN_ON_RELEASE` | `true` | run deterministic matching when a resource becomes AVAILABLE |
| `HIGH_UTILIZATION_THRESHOLD` / `CRITICAL_UTILIZATION_THRESHOLD` | `75` / `90` | capacity alert levels (%) |

## 13. Seed data

`python -m scripts.seed_data` drops and recreates all tables (the committed `flowcare_2.db` is the result of that script). It is deterministic apart from a single time anchor (the current UTC hour) and contains: 6 departments; 45 beds in all four statuses (23 occupied, each with exactly one patient); 34 patients (REGISTERED incl. 4 on the bed queue, ADMITTED, TRANSFERRED, discharge-ready admissions flagged in their admission notes, DISCHARGED); 4 theatres (AVAILABLE / IN_USE / CLEANING / UNAVAILABLE) with a realistic slot schedule (completed, booked, available, cancelled); 23 staff (AVAILABLE / ASSIGNED with active assignments / OFF_DUTY); surgeries in every lifecycle state; BED / THEATRE / STAFF waitlist entries; ~110 audit events with actors (`source=SEED`) including an auto-match example.

## 14. Tests

```bash
cd backend
python -m pytest -v -W error::sqlalchemy.exc.SAWarning
```
81 tests: inherited tests (updated for camelCase and the CLEANING release step), bed integrity, constraint-backed workflows on a file DB, thread-level concurrency (bed / slot / staff: exactly one winner), history & audit & actors, flow transitions, theatres/slots, surgeries, staff, waitlist ordering, matching (read-only, deterministic, confirm, auto-match, rejected auto-assignment keeps the release), capacity, realtime (after-commit only, failed ops silent, WebSocket), API contract (404/409/422, pagination, casing, OpenAPI, CORS) and seed consistency.

## 15. Frontend integration notes

* Read `/api/v1/openapi.json` (or `/docs`) for all schemas; every response is camelCase.
* Send `X-Actor-ID` / `X-Actor-Name` on mutations so the audit trail names the user.
* Use `/capacity` for dashboards — do not recompute counts from raw lists.
* Use `/waitlist` order as-is; use `/matches` to preview candidates and `/matches/confirm` (or the release endpoints with `autoAssign`) to act.
* Subscribe to `/api/v1/ws/capacity` and refresh on events; the WebSocket is a notification channel, not a source of truth.
* Pagination: read `X-Total-Count` (exposed via CORS) with `limit`/`offset`.
