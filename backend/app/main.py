from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api import projects
from app.config import settings
from app.db import app_db


@asynccontextmanager
async def lifespan(app: FastAPI):
    pool = await app_db.create_pool(settings.asyncpg_dsn)
    app.state.pool = pool
    try:
        yield
    finally:
        await app_db.close_pool(pool)


app = FastAPI(title=settings.APP_NAME, lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # dev only — restrict to real frontend origin(s) before production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# TODO: add auth back
app.include_router(projects.router)


@app.get("/health")
async def health_check() -> dict[str, str]:
    return {"status": "ok"}
