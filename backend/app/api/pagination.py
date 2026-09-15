"""Limit/offset pagination for list endpoints.

List endpoints keep returning bare JSON arrays (inherited contract). The total
number of matching rows is returned in the ``X-Total-Count`` response header.
"""
from dataclasses import dataclass

from fastapi import Query, Response

MAX_LIMIT = 500
DEFAULT_LIMIT = 100
TOTAL_COUNT_HEADER = "X-Total-Count"


@dataclass
class PaginationParams:
    limit: int
    offset: int


def get_pagination(
    limit: int = Query(DEFAULT_LIMIT, ge=1, le=MAX_LIMIT, description="Max items to return (1-500)"),
    offset: int = Query(0, ge=0, description="Items to skip"),
) -> PaginationParams:
    return PaginationParams(limit=limit, offset=offset)


def set_total_count(response: Response, total: int) -> None:
    response.headers[TOTAL_COUNT_HEADER] = str(total)
