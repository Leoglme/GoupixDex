"""GoupixDex FastAPI application."""

from __future__ import annotations

import logging

try:
    from dotenv import load_dotenv

    load_dotenv()
except ImportError:
    pass

from fastapi import FastAPI, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from config import get_settings
from routes import articles as articles_routes
from routes import auth as auth_routes
from routes import pricing_route
from routes import scan as scan_routes
from routes import settings_route
from routes import stats_route
from routes import users as users_routes

from core.win32_asyncio import ensure_proactor_event_loop

ensure_proactor_event_loop()

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s %(message)s")
logger = logging.getLogger("goupixdex")

settings = get_settings()

app = FastAPI(
    title="GoupixDex API",
    description="Pokémon TCG reselling backend for GoupixDex.",
    version="1.0.0",
)


@app.middleware("http")
async def log_errors_middleware(request: Request, call_next):  # type: ignore[no-untyped-def]
    try:
        return await call_next(request)
    except Exception:
        logger.exception("Request failed: %s %s", request.method, request.url.path)
        raise


_origins = [o.strip() for o in settings.cors_origins.split(",") if o.strip()]
app.add_middleware(
    CORSMiddleware,
    allow_origins=_origins if _origins != ["*"] else ["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(
    request: Request,
    exc: RequestValidationError,
) -> JSONResponse:
    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        content={"detail": exc.errors(), "body": exc.body},
    )


@app.exception_handler(Exception)
async def unhandled_exception_handler(
    request: Request,
    exc: Exception,
) -> JSONResponse:
    logger.exception("Unhandled error on %s %s", request.method, request.url.path)
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={
            "detail": str(exc) or "Internal Server Error",
            "error": "internal_server_error",
            "path": request.url.path,
        },
    )


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


app.include_router(auth_routes.router, prefix="/auth")
app.include_router(users_routes.router)
app.include_router(articles_routes.router)
app.include_router(settings_route.router)
app.include_router(pricing_route.router)
app.include_router(stats_route.router)
app.include_router(scan_routes.router)
