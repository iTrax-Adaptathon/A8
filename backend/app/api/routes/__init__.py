from app.api.routes.patients import router as patients_router
from app.api.routes.beds import router as beds_router
from app.api.routes.departments import router as departments_router
from app.api.routes.patient_flow import router as flow_router
from app.api.routes.capacity import router as capacity_router

__all__ = [
    "patients_router",
    "beds_router",
    "departments_router",
    "flow_router",
    "capacity_router",
]
