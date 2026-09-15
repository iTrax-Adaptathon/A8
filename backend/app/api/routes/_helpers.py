"""Small converters shared by route modules."""
from typing import List

from app.api.schemas import AutoAssignmentSchema, MatchCandidateSchema, MatchResultSchema
from app.application.matching_service import AutoAssignmentResult, MatchResult


def auto_assignment_schema(result: AutoAssignmentResult) -> AutoAssignmentSchema:
    return AutoAssignmentSchema(
        resource_type=result.resource_type,
        resource_id=result.resource_id,
        matched=result.matched,
        waitlist_entry_id=result.waitlist_entry_id,
        patient_id=result.patient_id,
        surgery_id=result.surgery_id,
        reason=result.reason,
        candidates_evaluated=result.candidates_evaluated,
        rejections=result.rejections,
    )


def auto_assignment_list(results: List[AutoAssignmentResult]) -> List[AutoAssignmentSchema]:
    return [auto_assignment_schema(r) for r in results]


def match_result_schema(result: MatchResult) -> MatchResultSchema:
    return MatchResultSchema(
        resource_type=result.resource_type,
        resource_id=result.resource_id,
        resource_available=result.resource_available,
        department_id=result.department_id,
        candidates=[
            MatchCandidateSchema(
                rank=c.rank,
                waitlist_entry_id=c.waitlist_entry.id,
                patient_id=c.patient_id,
                surgery_id=c.surgery_id,
                priority=c.waitlist_entry.priority,
                requested_at=c.waitlist_entry.requested_at,
                reason=c.reason,
            )
            for c in result.candidates
        ],
    )
