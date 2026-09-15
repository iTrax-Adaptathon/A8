from typing import List
from fastapi import APIRouter, Depends, Query, Response, status
from app.api.pagination import PaginationParams, get_pagination, set_total_count
from app.api.schemas import DepartmentCreateSchema, DepartmentResponseSchema
from app.application import DepartmentService
from app.core.dependencies import get_actor, get_department_service
from app.domain.entities import Actor, Department
from app.domain.policies import NotFoundError

router = APIRouter(prefix="/departments", tags=["Departments"])


@router.get("", response_model=List[DepartmentResponseSchema], summary="List departments")
def list_departments(
    response: Response,
    include_inactive: bool = Query(False, alias="includeInactive", description="Include deactivated departments"),
    pagination: PaginationParams = Depends(get_pagination),
    department_service: DepartmentService = Depends(get_department_service),
):
    departments = department_service.list_departments(
        include_inactive=include_inactive, limit=pagination.limit, offset=pagination.offset
    )
    set_total_count(response, department_service.count_departments(include_inactive))
    return [DepartmentResponseSchema.model_validate(d) for d in departments]


@router.get("/{id}", response_model=DepartmentResponseSchema, summary="Get department details")
def get_department(
    id: int,
    department_service: DepartmentService = Depends(get_department_service),
):
    department = department_service.get_department(id)
    if not department:
        raise NotFoundError(f"Department with id {id} not found")
    return DepartmentResponseSchema.model_validate(department)


@router.post("", response_model=DepartmentResponseSchema, status_code=status.HTTP_201_CREATED, summary="Create department")
def create_department(
    payload: DepartmentCreateSchema,
    department_service: DepartmentService = Depends(get_department_service),
    actor: Actor = Depends(get_actor),
):
    department = Department(
        id=None,
        name=payload.name,
        code=payload.code,
    )
    created = department_service.create_department(department, actor=actor)
    return DepartmentResponseSchema.model_validate(created)


@router.delete(
    "/{id}",
    response_model=DepartmentResponseSchema,
    summary="Deactivate department (soft delete; beds/theatres deactivated, history kept)",
)
def deactivate_department(
    id: int,
    department_service: DepartmentService = Depends(get_department_service),
    actor: Actor = Depends(get_actor),
):
    updated = department_service.deactivate_department(id, actor=actor)
    return DepartmentResponseSchema.model_validate(updated)
