from app.api.schemas.base import CamelModel, ErrorResponseSchema, UtcDateTime
from app.api.schemas.patient_schema import (
    PatientCreateSchema,
    PatientAdmitSchema,
    PatientTransferSchema,
    PatientDischargeSchema,
    PatientResponseSchema,
)
from app.api.schemas.bed_schema import (
    BedCreateSchema,
    BedStatusUpdateSchema,
    BedReleaseSchema,
    BedResponseSchema,
    BedReleaseResponseSchema,
)
from app.api.schemas.department_schema import (
    DepartmentCreateSchema,
    DepartmentResponseSchema,
)
from app.api.schemas.flow_event_schema import FlowEventResponseSchema
from app.api.schemas.capacity_schema import (
    DepartmentUtilizationSchema,
    CapacityMetricsSchema,
)
from app.api.schemas.match_schema import (
    AutoAssignmentSchema,
    MatchCandidateSchema,
    MatchResultSchema,
    MatchConfirmSchema,
)
from app.api.schemas.theatre_schema import (
    TheatreCreateSchema,
    TheatreStatusUpdateSchema,
    TheatreReleaseSchema,
    TheatreResponseSchema,
    TheatreReleaseResponseSchema,
    TheatreSlotCreateSchema,
    TheatreSlotCancelSchema,
    TheatreSlotResponseSchema,
    TheatreSlotCreateResponseSchema,
)
from app.api.schemas.surgery_schema import (
    SurgeryCreateSchema,
    SurgeryScheduleSchema,
    SurgeryActionSchema,
    SurgeryResponseSchema,
    SurgeryActionResponseSchema,
)
from app.api.schemas.staff_schema import (
    StaffCreateSchema,
    StaffStatusUpdateSchema,
    StaffAssignSchema,
    StaffAssignmentReleaseSchema,
    StaffResponseSchema,
    StaffAssignmentResponseSchema,
    StaffActionResponseSchema,
    StaffAssignmentReleaseResponseSchema,
)
from app.api.schemas.waitlist_schema import WaitlistCreateSchema, WaitlistResponseSchema

__all__ = [
    "CamelModel", "ErrorResponseSchema", "UtcDateTime",
    "PatientCreateSchema", "PatientAdmitSchema", "PatientTransferSchema", "PatientDischargeSchema", "PatientResponseSchema",
    "BedCreateSchema", "BedStatusUpdateSchema", "BedReleaseSchema", "BedResponseSchema", "BedReleaseResponseSchema",
    "DepartmentCreateSchema", "DepartmentResponseSchema",
    "FlowEventResponseSchema",
    "DepartmentUtilizationSchema", "CapacityMetricsSchema",
    "AutoAssignmentSchema", "MatchCandidateSchema", "MatchResultSchema", "MatchConfirmSchema",
    "TheatreCreateSchema", "TheatreStatusUpdateSchema", "TheatreReleaseSchema", "TheatreResponseSchema",
    "TheatreReleaseResponseSchema", "TheatreSlotCreateSchema", "TheatreSlotCancelSchema",
    "TheatreSlotResponseSchema", "TheatreSlotCreateResponseSchema",
    "SurgeryCreateSchema", "SurgeryScheduleSchema", "SurgeryActionSchema", "SurgeryResponseSchema", "SurgeryActionResponseSchema",
    "StaffCreateSchema", "StaffStatusUpdateSchema", "StaffAssignSchema", "StaffAssignmentReleaseSchema",
    "StaffResponseSchema", "StaffAssignmentResponseSchema", "StaffActionResponseSchema", "StaffAssignmentReleaseResponseSchema",
    "WaitlistCreateSchema", "WaitlistResponseSchema",
]
