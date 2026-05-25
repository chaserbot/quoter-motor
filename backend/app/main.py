import logging
import asyncio
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.routes import quotes, inventory, debug
from app.config import get_settings
from app.flex.client import FlexClient

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s — %(message)s",
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Warm the element cache in the background on startup so first search is instant
    settings = get_settings()
    client = FlexClient(base_url=settings.flex_base_url, api_key=settings.flex_api_key)
    async def warm_and_close() -> None:
        try:
            await client.warm_cache(ttl=settings.inventory_cache_ttl)
        except Exception:
            logger.exception("Cache warm-up failed")
        finally:
            await client.close()

    app.state.warmup_task = asyncio.create_task(warm_and_close())
    logger.info("Cache warm-up started in background")
    try:
        yield
    finally:
        app.state.warmup_task.cancel()
        try:
            await app.state.warmup_task
        except asyncio.CancelledError:
            pass


app = FastAPI(
    title="Quoter Motor",
    description="Recreate Flex quotes with current inventory and AI-matched equivalents",
    version="0.1.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(quotes.router)
app.include_router(inventory.router)
app.include_router(debug.router)


@app.get("/")
async def root():
    return {"service": "quoter-motor-api", "status": "running"}
