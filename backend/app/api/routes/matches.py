from fastapi import APIRouter, Depends, Query
from app.api.routes._helpers import auto_assignment_schema, match_result_schema
from app.api.schemas import AutoAssignmentSchema, MatchConfirmSchema, MatchResultSchema
from app.application import MatchingService
from app.core.dependencies import get_actor, get_matching_service
from app.domain.entities import Actor
from app.domain.enums import ResourceType

router = APIRouter(prefix="/matches", tags=["Matches"])


@router.get(
    "",
    response_model=MatchResultSchema,
    summary="Compute eligible waiting candidates for a resource (read-only, deterministic)",
    description="Nothing is written. Candidates are returned in queue order (priority, requestedAt, id) with a reason. "
    "resourceType: BED (bed id), THEATRE_SLOT (slot id) or STAFF (staff id).",
)
def find_matches(
    resource_type: ResourceType = Query(..., alias="resourceType"),
    resource_id: int = Query(..., alias="resourceId"),
    service: MatchingService = Depends(get_matching_service),
):
    return match_result_schema(service.find_candidates(resource_type, resource_id))


@router.post(
    "/confirm",
    response_model=AutoAssignmentSchema,
    summary="Confirm a match: performs the standard validated assignment workflow",
    description="Records MATCH_IDENTIFIED and then admits/transfers, schedules or assigns exactly as the manual "
    "endpoint would. A failed assignment is rolled back and recorded as ASSIGNMENT_REJECTED (409).",
)
def confirm_match(
    payload: MatchConfirmSchema,
    service: MatchingService = Depends(get_matching_service),
    actor: Actor = Depends(get_actor),
):
    result = service.confirm(
        payload.resource_type, payload.resource_id, payload.waitlist_entry_id, actor=actor, notes=payload.notes or ""
    )
    return auto_assignment_schema(result)
