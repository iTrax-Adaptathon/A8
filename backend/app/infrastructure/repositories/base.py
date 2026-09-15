from typing import Optional

from sqlalchemy.orm import Session


class BaseRepository:
    """Repositories never commit. They add/flush/execute inside the caller's
    transaction so that a whole workflow commits (or rolls back) as one unit."""

    def __init__(self, db: Session):
        self.db = db

    def flush(self) -> None:
        self.db.flush()

    @staticmethod
    def _paginate(query, limit: Optional[int], offset: int):
        if offset:
            query = query.offset(offset)
        if limit is not None:
            query = query.limit(limit)
        return query

    def _count(self, query) -> int:
        # Query.count() wraps the filtered query in a subquery, so it stays
        # correct even when no WHERE clause is present.
        return query.order_by(None).count()
