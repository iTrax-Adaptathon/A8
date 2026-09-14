from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import settings
from app.core.exception_handlers import register_exception_handlers
from app.infrastructure.database import Base, engine
from app.api.routes import (
    patients_router,
    beds_router,
    departments_router,
    flow_router,
    capacity_router,
)


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup: Create tables if not existing
    Base.metadata.create_all(bind=engine)
    yield


app = FastAPI(
    title=settings.PROJECT_NAME,
    description=(
        "FlowCare_2 — Hospital Capacity & Patient Flow Platform Backend.\n"
        "Features layered architecture, capacity intelligence engine, patient flow orchestration, "
        "and configurable utilization thresholds."
    ),
    version="2.0.0",
    openapi_url=f"{settings.API_V1_STR}/openapi.json",
    docs_url="/docs",
    redoc_url="/redoc",
    lifespan=lifespan,
)

# Enable CORS for Flutter Web / Desktop frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Register custom domain exception handlers
register_exception_handlers(app)

# Include Routers under /api/v1
app.include_router(patients_router, prefix=settings.API_V1_STR)
app.include_router(beds_router, prefix=settings.API_V1_STR)
app.include_router(departments_router, prefix=settings.API_V1_STR)
app.include_router(flow_router, prefix=settings.API_V1_STR)
app.include_router(capacity_router, prefix=settings.API_V1_STR)


@app.get("/", tags=["Health"])
def root():
    return {
        "status": "online",
        "app": settings.PROJECT_NAME,
        "version": "2.0.0",
        "docs": "/docs",
    }
