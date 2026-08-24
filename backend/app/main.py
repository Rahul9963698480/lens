import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.exception_handlers import request_validation_exception_handler
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware

from app.api import projects, sql_routes
from app.config import settings
from app.db import app_db

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    pool = await app_db.create_pool(settings.asyncpg_dsn)
    app.state.pool = pool
    try:
        yield
    finally:
        await app_db.close_pool(pool)


app = FastAPI(title=settings.APP_NAME, lifespan=lifespan)


@app.exception_handler(RequestValidationError)
async def log_request_validation_error(
    request: Request, exc: RequestValidationError
):
    logger.warning(
        "422 %s %s errors=%s body=%r",
        request.method,
        request.url.path,
        exc.errors(),
        exc.body,
    )
    return await request_validation_exception_handler(request, exc)


app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # dev only — restrict to real frontend origin(s) before production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# TODO: add auth back
app.include_router(projects.router)
app.include_router(sql_routes.router)


@app.get("/health")
async def health_check() -> dict[str, str]:
    return {"status": "ok"}
