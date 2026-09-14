from typing import List, Optional
from app.infrastructure.repositories import BedRepository
from app.domain.entities import Bed
from app.domain.enums import BedStatus, BedType


class BedService:
    def __init__(self, bed_repo: BedRepository):
        self.bed_repo = bed_repo

    def create_bed(self, bed: Bed) -> Bed:
        return self.bed_repo.create(bed)

    def get_bed(self, bed_id: int) -> Optional[Bed]:
        return self.bed_repo.get_by_id(bed_id)

    def list_beds(
        self,
        department_id: Optional[int] = None,
        status: Optional[BedStatus] = None,
        bed_type: Optional[BedType] = None,
    ) -> List[Bed]:
        return self.bed_repo.get_all(department_id=department_id, status=status, bed_type=bed_type)

    def update_bed_status(self, bed_id: int, new_status: BedStatus) -> Bed:
        bed = self.bed_repo.get_by_id(bed_id)
        if not bed:
            raise ValueError(f"Bed with id {bed_id} not found")
        bed.status = new_status
        if new_status in (BedStatus.AVAILABLE, BedStatus.CLEANING, BedStatus.MAINTENANCE):
            bed.current_patient_id = None
        return self.bed_repo.update(bed)
