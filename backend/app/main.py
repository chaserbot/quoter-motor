import logging
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.routes import quotes, inventory, debug

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s — %(message)s",
)

app = FastAPI(
    title="Quoter Motor",
    description="Recreate Flex quotes with current inventory and AI-matched equivalents",
    version="0.1.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Tightened in production via nginx
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
