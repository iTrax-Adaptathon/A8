import logging
from fastapi import Request, status
from fastapi.responses import JSONResponse
from sqlalchemy.exc import IntegrityError
from app.domain.policies import (
    ConflictError,
    DomainValidationError,
    NotFoundError,
)

logger = logging.getLogger(__name__)


def _error_response(status_code: int, code: str, message: str) -> JSONResponse:
    return JSONResponse(status_code=status_code, content={"error": code, "message": message})


def register_exception_handlers(app):
    """HTTP mapping of domain errors:

    * 404 NOT_FOUND            - referenced entity does not exist
    * 409 CONFLICT             - state/resource conflict (invalid transition,
                                 double booking, lost concurrent claim,
                                 database constraint violation)
    * 422 DOMAIN_VALIDATION_ERROR - business validation failure
    """

    @app.exception_handler(NotFoundError)
    async def not_found_handler(request: Request, exc: NotFoundError):
        return _error_response(status.HTTP_404_NOT_FOUND, "NOT_FOUND", str(exc))

    @app.exception_handler(ConflictError)
    async def conflict_handler(request: Request, exc: ConflictError):
        logger.info("Conflict: %s", exc)
        return _error_response(status.HTTP_409_CONFLICT, "CONFLICT", str(exc))

    @app.exception_handler(DomainValidationError)
    async def domain_validation_handler(request: Request, exc: DomainValidationError):
        logger.warning("Domain validation error: %s", exc)
        return _error_response(status.HTTP_422_UNPROCESSABLE_CONTENT, "DOMAIN_VALIDATION_ERROR", str(exc))

    @app.exception_handler(IntegrityError)
    async def integrity_handler(request: Request, exc: IntegrityError):
        # A constraint refused the write; the session was rolled back by get_db.
        logger.warning("Integrity error: %s", exc.orig)
        return _error_response(
            status.HTTP_409_CONFLICT,
            "CONFLICT",
            "The operation violates a database integrity constraint and was rolled back.",
        )
