from app.api.routes.patients import router as patients_router
from app.api.routes.beds import router as beds_router
from app.api.routes.departments import router as departments_router
from app.api.routes.patient_flow import router as flow_router
from app.api.routes.capacity import router as capacity_router
from app.api.routes.theatres import router as theatres_router, slots_router as theatre_slots_router
from app.api.routes.surgeries import router as surgeries_router
from app.api.routes.staff import router as staff_router, assignments_router as staff_assignments_router
from app.api.routes.waitlist import router as waitlist_router
from app.api.routes.matches import router as matches_router
from app.api.routes.realtime import router as realtime_router

__all__ = [
    "patients_router",
    "beds_router",
    "departments_router",
    "flow_router",
    "capacity_router",
    "theatres_router",
    "theatre_slots_router",
    "surgeries_router",
    "staff_router",
    "staff_assignments_router",
    "waitlist_router",
    "matches_router",
    "realtime_router",
]
