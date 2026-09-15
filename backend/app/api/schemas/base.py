from datetime import datetime, timezone
from typing import Annotated, Any, Optional

from pydantic import AfterValidator, BaseModel, ConfigDict, field_serializer
from pydantic.alias_generators import to_camel


def _to_naive_utc(value: Any) -> Any:
    """Normalise incoming datetimes to naive UTC (the storage form)."""
    if isinstance(value, datetime) and value.tzinfo is not None:
        return value.astimezone(timezone.utc).replace(tzinfo=None)
    return value


# Request datetime type: accepts ISO-8601 with or without offset, stored as UTC.
UtcDateTime = Annotated[datetime, AfterValidator(_to_naive_utc)]


class CamelModel(BaseModel):
    """Base for every API schema.

    * Responses are serialised in camelCase.
    * Requests accept camelCase *and* snake_case (``populate_by_name``).
    * Naive datetimes (stored UTC) are emitted with an explicit ``Z``/+00:00.
    """

    model_config = ConfigDict(
        alias_generator=to_camel,
        populate_by_name=True,
        from_attributes=True,
        use_enum_values=False,
    )

    @field_serializer("*", when_used="json")
    def _serialize_datetimes(self, value: Any, _info):
        if isinstance(value, datetime) and value.tzinfo is None:
            return value.replace(tzinfo=timezone.utc)
        return value


class ErrorResponseSchema(CamelModel):
    error: str
    message: str
