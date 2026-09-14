from fastapi import APIRouter, Depends
from app.api.schemas import CapacityMetricsSchema
from app.application import CapacityIntelligenceService
from app.core.dependencies import get_capacity_service

router = APIRouter(prefix="/capacity", tags=["Capacity Intelligence"])


@router.get("", response_model=CapacityMetricsSchema, summary="Get real-time capacity intelligence metrics")
def get_capacity_metrics(
    capacity_service: CapacityIntelligenceService = Depends(get_capacity_service),
):
    metrics = capacity_service.calculate_hospital_capacity()
    return CapacityMetricsSchema.model_validate(metrics)
