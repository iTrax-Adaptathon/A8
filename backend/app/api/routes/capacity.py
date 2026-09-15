from fastapi import APIRouter, Depends
from app.api.schemas import CapacityMetricsSchema
from app.application import CapacityIntelligenceService
from app.core.dependencies import get_capacity_service

router = APIRouter(prefix="/capacity", tags=["Capacity Intelligence"])


@router.get(
    "",
    response_model=CapacityMetricsSchema,
    summary="Live capacity snapshot: beds, theatres, staff, queues and department occupancy",
    description="All counts come from the current database state. `available` always means assignable right now "
    "(CLEANING / MAINTENANCE / UNAVAILABLE / IN_USE / inactive resources are never counted as available).",
)
def get_capacity_metrics(
    capacity_service: CapacityIntelligenceService = Depends(get_capacity_service),
):
    metrics = capacity_service.calculate_hospital_capacity()
    return CapacityMetricsSchema.model_validate(metrics)
