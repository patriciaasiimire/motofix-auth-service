# motofix-auth-service/app/main.py

import os
import logging
from fastapi import FastAPI
import asyncpg
from contextlib import asynccontextmanager

from .routers import auth
from app.core.cors import setup_cors

# Configure logging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger("motofix-auth")

# ────────────────────────────── DATABASE POOL ──────────────────────────────

pool: asyncpg.Pool

@asynccontextmanager
async def lifespan(app: FastAPI):
    global pool
    # Use Render's internal DATABASE_URL
    pool = await asyncpg.create_pool(dsn=os.getenv("DATABASE_URL"))
    yield
    await pool.close()

app = FastAPI(
    title="MOTOFIX Auth Service",
    description="Secure phone + OTP login for customers and mechanics in Uganda",
    version="1.0.0",
    lifespan=lifespan
)

@app.get("/health")
async def health_check():
    return {"status": "ok"}

# ────────────────────────────── CORS (CENTRALIZED) ──────────────────────────────
# Import and apply centralized CORS configuration from app.core.cors
setup_cors(app)

# ────────────────────────────── STARTUP EVENT ──────────────────────────────

@app.on_event("startup")
async def startup_event():
    for route in app.routes:
        if hasattr(route, "path") and route.path == "/health":
            print(f"Route: {route.path} - {route.name}")
    logger.info("=" * 70)
    logger.info("🚀 MOTOFIX Auth Service Starting")
    logger.info("=" * 70)

# ────────────────────────────── DEPENDENCY ──────────────────────────────
# Make pool available to routers
def get_pool():
    return pool

# Pass pool to auth router if needed (or use dependency injection in router)
auth_router = auth.router
app.include_router(auth_router, prefix="/auth")

# ────────────────────────────── GLOBAL EXCEPTION HANDLER ──────────────────────────────

from fastapi import Request
from fastapi.responses import JSONResponse

@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    logger.error(f"❌ [Global Exception] Type: {type(exc).__name__}")
    logger.error(f"❌ [Global Exception] Path: {request.url.path}")
    logger.error(f"❌ [Global Exception] Origin: {request.headers.get('origin', 'unknown')}")
    logger.error(f"❌ [Global Exception] Details: {str(exc)}")
    return JSONResponse(
        status_code=500,
        content={"error_type": type(exc).__name__, "message": str(exc)}
    )