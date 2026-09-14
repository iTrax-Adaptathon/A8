from typing import List
from fastapi import APIRouter, Depends, status, HTTPException
from app.api.schemas import DepartmentCreateSchema, DepartmentResponseSchema
from app.application import DepartmentService
from app.core.dependencies import get_department_service
from app.domain.entities import Department

router = APIRouter(prefix="/departments", tags=["Departments"])


@router.get("", response_model=List[DepartmentResponseSchema], summary="List departments")
def list_departments(
    department_service: DepartmentService = Depends(get_department_service),
):
    departments = department_service.list_departments()
    return [DepartmentResponseSchema.model_validate(d) for d in departments]


@router.get("/{id}", response_model=DepartmentResponseSchema, summary="Get department details")
def get_department(
    id: int,
    department_service: DepartmentService = Depends(get_department_service),
):
    department = department_service.get_department(id)
    if not department:
        raise HTTPException(status_code=404, detail=f"Department {id} not found")
    return DepartmentResponseSchema.model_validate(department)


@router.post("", response_model=DepartmentResponseSchema, status_code=status.HTTP_201_CREATED, summary="Create department")
def create_department(
    payload: DepartmentCreateSchema,
    department_service: DepartmentService = Depends(get_department_service),
):
    department = Department(
        id=None,
        name=payload.name,
        code=payload.code,
    )
    created = department_service.create_department(department)
    return DepartmentResponseSchema.model_validate(created)
