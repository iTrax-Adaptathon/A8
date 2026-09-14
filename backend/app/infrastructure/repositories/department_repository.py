from typing import List, Optional
from sqlalchemy.orm import Session
from sqlalchemy import func
from app.infrastructure.database.models import DepartmentModel, BedModel
from app.domain.entities import Department
from app.domain.enums import BedStatus


class DepartmentRepository:
    def __init__(self, db: Session):
        self.db = db

    def get_by_id(self, department_id: int) -> Optional[Department]:
        model = self.db.query(DepartmentModel).filter(DepartmentModel.id == department_id).first()
        if not model:
            return None
        occupied_count = (
            self.db.query(func.count(BedModel.id))
            .filter(
                BedModel.department_id == department_id,
                BedModel.status == BedStatus.OCCUPIED.value,
            )
            .scalar()
            or 0
        )
        return model.to_entity(occupied_count=occupied_count)

    def get_all(self) -> List[Department]:
        models = self.db.query(DepartmentModel).order_by(DepartmentModel.name.asc()).all()
        result = []
        for m in models:
            occupied_count = (
                self.db.query(func.count(BedModel.id))
                .filter(
                    BedModel.department_id == m.id,
                    BedModel.status == BedStatus.OCCUPIED.value,
                )
                .scalar()
                or 0
            )
            result.append(m.to_entity(occupied_count=occupied_count))
        return result

    def create(self, department: Department) -> Department:
        model = DepartmentModel.from_entity(department)
        self.db.add(model)
        self.db.commit()
        self.db.refresh(model)
        return model.to_entity(occupied_count=0)
