"""Crypto Signals API — thin entry point.

All business logic lives in services/, all endpoints in routes/.
"""
from fastapi import FastAPI, APIRouter
from starlette.middleware.cors import CORSMiddleware
import logging

from core import db, client  # noqa: F401 — keep reference alive
from services.bot_loop import _start_bot

# Routers — each defines its own APIRouter under `router = APIRouter()`
from routes import auth, market, signals, watchlist, portfolio
from routes import notifications, binance, premium, bot, backtest, predict

# ---- logging setup ----
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
)
logger = logging.getLogger("server")

# ---- FastAPI app ----
app = FastAPI(title="Crypto Signals API")
api_router = APIRouter(prefix="/api")

# Mount all routers
for module in (
    auth, market, signals, watchlist, portfolio,
    notifications, binance, premium, bot, backtest, predict,
):
    api_router.include_router(module.router)

app.include_router(api_router)

# ---- CORS ----
app.add_middleware(
    CORSMiddleware,
    allow_credentials=True,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


# ---- Root & lifecycle ----
@app.get("/api/")
async def root():
    return {"name": "Crypto Signals API", "version": "1.0"}


@app.get("/api/health")
async def health():
    """Lightweight health probe for deployment monitors (Emergent, Hetzner, etc.).
    Returns 200 + DB ping result. Used by load balancers and uptime monitors."""
    try:
        # Minimal MongoDB ping (no auth needed for `ping`)
        await client.admin.command("ping")
        db_ok = True
    except Exception:
        db_ok = False
    return {
        "ok": True,
        "service": "signalx-api",
        "version": "1.0",
        "db": db_ok,
    }


@app.on_event("startup")
async def startup_event():
    """Spawn the bot engine background loop."""
    logger.info("SignalX API starting (production-ready)")
    await _start_bot()


@app.on_event("shutdown")
async def shutdown_db_client():
    logger.info("SignalX API shutting down")
    client.close()
