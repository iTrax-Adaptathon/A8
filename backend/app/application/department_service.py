from typing import List, Optional
from app.infrastructure.repositories import DepartmentRepository
from app.domain.entities import Department


class DepartmentService:
    def __init__(self, department_repo: DepartmentRepository):
        self.department_repo = department_repo

    def create_department(self, department: Department) -> Department:
        return self.department_repo.create(department)

    def get_department(self, department_id: int) -> Optional[Department]:
        return self.department_repo.get_by_id(department_id)

    def list_departments(self) -> List[Department]:
        return self.department_repo.get_all()
