import asyncio
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import settings
from app.core.exception_handlers import register_exception_handlers
from app.infrastructure.database import Base, engine
from app.realtime.event_bus import event_bus
from app.api.routes import (
    patients_router,
    beds_router,
    departments_router,
    flow_router,
    capacity_router,
    theatres_router,
    theatre_slots_router,
    surgeries_router,
    staff_router,
    staff_assignments_router,
    waitlist_router,
    matches_router,
    realtime_router,
)

API_DESCRIPTION = """
FlowCare_2 — Hospital Capacity, Patient Flow & Resource Orchestration backend.

**This system contains no LLM, RAG, machine learning or AI-based operational
decision-making. All decisions use deterministic predefined business rules.**

Conventions
* JSON responses are camelCase; requests accept camelCase and snake_case.
* List endpoints return bare arrays, accept `limit` (1-500) / `offset` and set `X-Total-Count`.
* Errors: 404 not found, 409 state/resource conflict, 422 validation. Body: `{"error", "message"}`.
* Actor tracking: send `X-Actor-ID` and `X-Actor-Name` headers (default `system` / `System`).
* Realtime: WebSocket `/api/v1/ws/capacity` emits small events strictly after commit (see GET /api/v1/realtime).
* Queue order: priority ASC, requestedAt ASC, id ASC. Matching is deterministic (see README).
"""


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup: create tables if not existing, bind the realtime bus to the server loop.
    Base.metadata.create_all(bind=engine)
    event_bus.bind_loop(asyncio.get_running_loop())
    yield
    event_bus.unbind_loop()


app = FastAPI(
    title=settings.PROJECT_NAME,
    description=API_DESCRIPTION,
    version="2.1.0",
    openapi_url=f"{settings.API_V1_STR}/openapi.json",
    docs_url="/docs",
    redoc_url="/redoc",
    lifespan=lifespan,
)

# CORS for the separately developed React/Vite frontend (configurable via CORS_ORIGINS).
app.add_middleware(
    CORSMiddleware,
    allow_origins=list(settings.CORS_ORIGINS),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["X-Total-Count"],
)

# Register custom domain exception handlers
register_exception_handlers(app)

# Include Routers under /api/v1
for router in (
    patients_router,
    beds_router,
    departments_router,
    flow_router,
    capacity_router,
    theatres_router,
    theatre_slots_router,
    surgeries_router,
    staff_router,
    staff_assignments_router,
    waitlist_router,
    matches_router,
    realtime_router,
):
    app.include_router(router, prefix=settings.API_V1_STR)


@app.get("/", tags=["Health"])
def root():
    return {
        "status": "online",
        "app": settings.PROJECT_NAME,
        "version": "2.1.0",
        "docs": "/docs",
        "openapi": f"{settings.API_V1_STR}/openapi.json",
        "websocket": f"{settings.API_V1_STR}/ws/capacity",
    }
