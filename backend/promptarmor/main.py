import logging
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from promptarmor.config import settings
from promptarmor.database import get_db, init_db
from promptarmor.routers import attacks, eval, system_prompts, taxonomy

logging.basicConfig(level=settings.log_level.upper())
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None]:
    logger.info("Starting PromptArmor backend...")
    await init_db()
    yield
    logger.info("Shutting down PromptArmor backend.")


app = FastAPI(
    title="PromptArmor",
    description="Interactive prompt injection defense testing sandbox",
    version="0.1.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


app.include_router(taxonomy.router)
app.include_router(attacks.router)
app.include_router(system_prompts.router)
app.include_router(eval.router)


@app.get("/api/v1/health")
async def health_check() -> dict[str, str]:
    """Verify the server is running and the database is connected."""
    async with get_db() as db:
        cursor = await db.execute("SELECT 1")
        await cursor.fetchone()
    return {"status": "ok", "database": "connected"}
