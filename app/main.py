import logging
from typing import Any

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.core.config import get_settings
from app.database.session import Base, engine
from app.routers import auth, chat, documents

settings = get_settings()
logging.basicConfig(level=logging.DEBUG if settings.debug else logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(
    title=settings.app_name,
    debug=settings.debug,
    docs_url=f"{settings.api_v1_prefix}/docs",
    openapi_url=f"{settings.api_v1_prefix}/openapi.json",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[str(origin) for origin in settings.cors_origins],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
def on_startup() -> None:
    Base.metadata.create_all(bind=engine)
    logger.info("Application startup complete")


@app.exception_handler(StarletteHTTPException)
async def http_exception_handler(
    request: Request,
    exc: StarletteHTTPException,
) -> JSONResponse:
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "success": False,
            "error": {
                "type": "http_error",
                "message": exc.detail,
            },
        },
    )


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(
    request: Request,
    exc: RequestValidationError,
) -> JSONResponse:
    return JSONResponse(
        status_code=422,
        content={
            "success": False,
            "error": {
                "type": "validation_error",
                "message": "Request validation failed",
                "details": exc.errors(),
            },
        },
    )


@app.exception_handler(Exception)
async def unhandled_exception_handler(
    request: Request,
    exc: Exception,
) -> JSONResponse:
    logger.exception("Unhandled exception")
    return JSONResponse(
        status_code=500,
        content={
            "success": False,
            "error": {
                "type": "internal_error",
                "message": "An unexpected error occurred",
            },
        },
    )


@app.get("/health")
async def health_check() -> dict[str, Any]:
    return {"status": "ok", "service": settings.app_name}


app.include_router(auth.router, prefix=settings.api_v1_prefix)
app.include_router(documents.router, prefix=settings.api_v1_prefix)
app.include_router(chat.router, prefix=settings.api_v1_prefix)
