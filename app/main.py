# motofix-auth-service/app/main.py

import os
import logging
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import asyncpg
from contextlib import asynccontextmanager

from .routers import auth
from pathlib import Path
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse

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

# ────────────────────────────── CORS ──────────────────────────────
# Allow your frontend to call this service
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "https://customer.motofix.org",
        "https://admin.motofix.org",
        "https://motofix-driver-assist.onrender.com",
        "https://motofixug.onrender.com",
        # Local development URLs
        "http://localhost:3000",
        "http://localhost:8080",
        "http://localhost:5173",
    ],
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["*"],
)

# ────────────────────────────── STARTUP EVENT ──────────────────────────────

@app.on_event("startup")
async def startup_event():
    logger.info("=" * 60)
    logger.info("🚀 MOTOFIX Auth Service Starting")
    logger.info("=" * 60)
    logger.info("✅ CORS Enabled for:")
    logger.info("   • https://customer.motofix.org")
    logger.info("   • https://admin.motofix.org")
    logger.info("   • https://motofix-driver-assist.onrender.com")
    logger.info("   • https://motofixug.onrender.com")
    logger.info("   • localhost:3000, 8080, 5173 (dev)")
    logger.info("✅ Credentials allowed: Yes (httpOnly cookies + Bearer tokens)")
    logger.info("=" * 60)

# ────────────────────────────── DEPENDENCY ──────────────────────────────
# Make pool available to routers
def get_pool():
    return pool

# Pass pool to auth router if needed (or use dependency injection in router)
app.include_router(auth.router)

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

# ────────────────────────────── STATIC / SPA FALLBACK ──────────────────────────────
# If you bundle the frontend with this service, set the `FRONTEND_DIST` env var
# (path to built SPA, e.g. `dist` or `build`). When present, serve static files
# and return index.html for unknown paths so client-side routing works.
frontend_dir = os.getenv(
    "FRONTEND_DIST",
    str(Path(__file__).resolve().parents[1] / "frontend")
)
frontend_path = Path(frontend_dir)
index_file = frontend_path / "index.html"

if frontend_path.exists() and index_file.exists():
    app.mount("/", StaticFiles(directory=str(frontend_path), html=True), name="frontend")

    @app.get("/{full_path:path}", include_in_schema=False)
    async def spa_fallback(full_path: str):
        return FileResponse(index_file)