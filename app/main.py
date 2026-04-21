from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.api import places, projects
from app.cache import close_redis
from app.database import Base, engine


@asynccontextmanager
async def lifespan(_: FastAPI):
    # for a real project this would be `alembic upgrade head`
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    try:
        yield
    finally:
        await engine.dispose()
        await close_redis()


app = FastAPI(
    title="Travel Planner",
    version="0.1.0",
    description="CRUD for travel projects and places imported from the Art Institute of Chicago",
    lifespan=lifespan,
)

app.include_router(projects.router)
app.include_router(places.router)


@app.get("/health", tags=["meta"])
async def health() -> dict[str, str]:
    return {"status": "ok"}
