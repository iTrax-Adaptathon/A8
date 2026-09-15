from datetime import datetime
from typing import Dict, List, Optional
from sqlalchemy import func, update
from sqlalchemy.orm import Session
from app.infrastructure.database.models import TheatreModel, TheatreSlotModel
from app.infrastructure.repositories.base import BaseRepository
from app.domain.entities import Theatre, TheatreSlot
from app.domain.enums import TheatreStatus, TheatreSlotStatus


class TheatreRepository(BaseRepository):
    def __init__(self, db: Session):
        super().__init__(db)

    def get_by_id(self, theatre_id: int) -> Optional[Theatre]:
        model = self.db.get(TheatreModel, theatre_id)
        return model.to_entity() if model else None

    def _base_query(
        self,
        department_id: Optional[int] = None,
        status: Optional[TheatreStatus] = None,
        include_inactive: bool = False,
    ):
        query = self.db.query(TheatreModel)
        if not include_inactive:
            query = query.filter(TheatreModel.is_active.is_(True))
        if department_id:
            query = query.filter(TheatreModel.department_id == department_id)
        if status:
            query = query.filter(TheatreModel.status == status.value)
        return query

    def get_all(
        self,
        department_id: Optional[int] = None,
        status: Optional[TheatreStatus] = None,
        include_inactive: bool = False,
        limit: Optional[int] = None,
        offset: int = 0,
    ) -> List[Theatre]:
        query = self._base_query(department_id, status, include_inactive).order_by(
            TheatreModel.name.asc(), TheatreModel.id.asc()
        )
        return [m.to_entity() for m in self._paginate(query, limit, offset).all()]

    def count(
        self,
        department_id: Optional[int] = None,
        status: Optional[TheatreStatus] = None,
        include_inactive: bool = False,
    ) -> int:
        return self._count(self._base_query(department_id, status, include_inactive))

    def count_by_status(self) -> Dict[str, int]:
        counts = {s.value: 0 for s in TheatreStatus}
        rows = (
            self.db.query(TheatreModel.status, func.count(TheatreModel.id))
            .filter(TheatreModel.is_active.is_(True))
            .group_by(TheatreModel.status)
            .all()
        )
        for status_value, n in rows:
            counts[status_value] = n
        return counts

    def create(self, theatre: Theatre) -> Theatre:
        model = TheatreModel.from_entity(theatre)
        self.db.add(model)
        self.db.flush()
        return model.to_entity()

    def set_status_if(self, theatre_id: int, expected: TheatreStatus, new_status: TheatreStatus) -> bool:
        result = self.db.execute(
            update(TheatreModel)
            .where(
                TheatreModel.id == theatre_id,
                TheatreModel.status == expected.value,
                TheatreModel.is_active.is_(True),
            )
            .values(status=new_status.value)
        )
        return result.rowcount == 1

    def set_active(self, theatre_id: int, is_active: bool) -> bool:
        result = self.db.execute(
            update(TheatreModel)
            .where(TheatreModel.id == theatre_id, TheatreModel.is_active.is_(not is_active))
            .values(is_active=is_active)
        )
        return result.rowcount == 1

    def deactivate_by_department(self, department_id: int) -> int:
        result = self.db.execute(
            update(TheatreModel)
            .where(TheatreModel.department_id == department_id, TheatreModel.is_active.is_(True))
            .values(is_active=False)
        )
        return result.rowcount


class TheatreSlotRepository(BaseRepository):
    def __init__(self, db: Session):
        super().__init__(db)

    def get_by_id(self, slot_id: int) -> Optional[TheatreSlot]:
        model = self.db.get(TheatreSlotModel, slot_id)
        return model.to_entity() if model else None

    def _base_query(
        self,
        theatre_id: Optional[int] = None,
        status: Optional[TheatreSlotStatus] = None,
        surgery_id: Optional[int] = None,
        start_from: Optional[datetime] = None,
        start_to: Optional[datetime] = None,
    ):
        query = self.db.query(TheatreSlotModel)
        if theatre_id:
            query = query.filter(TheatreSlotModel.theatre_id == theatre_id)
        if status:
            query = query.filter(TheatreSlotModel.status == status.value)
        if surgery_id:
            query = query.filter(TheatreSlotModel.surgery_id == surgery_id)
        if start_from:
            query = query.filter(TheatreSlotModel.start_time >= start_from)
        if start_to:
            query = query.filter(TheatreSlotModel.start_time <= start_to)
        return query

    def get_all(
        self,
        theatre_id: Optional[int] = None,
        status: Optional[TheatreSlotStatus] = None,
        surgery_id: Optional[int] = None,
        start_from: Optional[datetime] = None,
        start_to: Optional[datetime] = None,
        limit: Optional[int] = None,
        offset: int = 0,
    ) -> List[TheatreSlot]:
        query = self._base_query(theatre_id, status, surgery_id, start_from, start_to).order_by(
            TheatreSlotModel.start_time.asc(), TheatreSlotModel.id.asc()
        )
        return [m.to_entity() for m in self._paginate(query, limit, offset).all()]

    def count(
        self,
        theatre_id: Optional[int] = None,
        status: Optional[TheatreSlotStatus] = None,
        surgery_id: Optional[int] = None,
        start_from: Optional[datetime] = None,
        start_to: Optional[datetime] = None,
    ) -> int:
        return self._count(self._base_query(theatre_id, status, surgery_id, start_from, start_to))

    def get_live_slots_for_theatre(self, theatre_id: int) -> List[TheatreSlot]:
        """All non-cancelled slots of a theatre (used for overlap checks)."""
        models = (
            self.db.query(TheatreSlotModel)
            .filter(
                TheatreSlotModel.theatre_id == theatre_id,
                TheatreSlotModel.status != TheatreSlotStatus.CANCELLED.value,
            )
            .order_by(TheatreSlotModel.start_time.asc(), TheatreSlotModel.id.asc())
            .all()
        )
        return [m.to_entity() for m in models]

    def count_booked_for_theatre(self, theatre_id: int) -> int:
        return self._count(
            self.db.query(TheatreSlotModel).filter(
                TheatreSlotModel.theatre_id == theatre_id,
                TheatreSlotModel.status == TheatreSlotStatus.BOOKED.value,
            )
        )

    def next_available_slot(self, after: datetime, theatre_ids: Optional[List[int]] = None) -> Optional[TheatreSlot]:
        query = self.db.query(TheatreSlotModel).filter(
            TheatreSlotModel.status == TheatreSlotStatus.AVAILABLE.value,
            TheatreSlotModel.start_time >= after,
        )
        if theatre_ids is not None:
            query = query.filter(TheatreSlotModel.theatre_id.in_(theatre_ids))
        model = query.order_by(TheatreSlotModel.start_time.asc(), TheatreSlotModel.id.asc()).first()
        return model.to_entity() if model else None

    def create(self, slot: TheatreSlot) -> TheatreSlot:
        model = TheatreSlotModel.from_entity(slot)
        self.db.add(model)
        self.db.flush()
        return model.to_entity()

    # Atomic compare-and-set
    def book_if_available(self, slot_id: int, surgery_id: int) -> bool:
        result = self.db.execute(
            update(TheatreSlotModel)
            .where(
                TheatreSlotModel.id == slot_id,
                TheatreSlotModel.status == TheatreSlotStatus.AVAILABLE.value,
                TheatreSlotModel.surgery_id.is_(None),
            )
            .values(status=TheatreSlotStatus.BOOKED.value, surgery_id=surgery_id)
        )
        return result.rowcount == 1

    def release_booking(self, slot_id: int, surgery_id: int) -> bool:
        result = self.db.execute(
            update(TheatreSlotModel)
            .where(
                TheatreSlotModel.id == slot_id,
                TheatreSlotModel.status == TheatreSlotStatus.BOOKED.value,
                TheatreSlotModel.surgery_id == surgery_id,
            )
            .values(status=TheatreSlotStatus.AVAILABLE.value, surgery_id=None)
        )
        return result.rowcount == 1

    def complete_booking(self, slot_id: int, surgery_id: int) -> bool:
        result = self.db.execute(
            update(TheatreSlotModel)
            .where(
                TheatreSlotModel.id == slot_id,
                TheatreSlotModel.status == TheatreSlotStatus.BOOKED.value,
                TheatreSlotModel.surgery_id == surgery_id,
            )
            .values(status=TheatreSlotStatus.COMPLETED.value)
        )
        return result.rowcount == 1

    def cancel_if_available(self, slot_id: int) -> bool:
        result = self.db.execute(
            update(TheatreSlotModel)
            .where(
                TheatreSlotModel.id == slot_id,
                TheatreSlotModel.status == TheatreSlotStatus.AVAILABLE.value,
            )
            .values(status=TheatreSlotStatus.CANCELLED.value)
        )
        return result.rowcount == 1
