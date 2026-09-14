import logging
from fastapi import Request, status
from fastapi.responses import JSONResponse
from app.domain.policies import DomainValidationError

logger = logging.getLogger(__name__)


def register_exception_handlers(app):
    @app.exception_handler(DomainValidationError)
    async def domain_validation_handler(request: Request, exc: DomainValidationError):
        logger.warning(f"Domain validation error: {str(exc)}")
        return JSONResponse(
            status_code=status.HTTP_400_BAD_REQUEST,
            content={
                "error": "DOMAIN_VALIDATION_ERROR",
                "message": str(exc),
            },
        )
