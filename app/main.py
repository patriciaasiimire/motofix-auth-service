# app/main.py

import os
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import asyncpg
from contextlib import asynccontextmanager

from .routers import auth

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
        "https://motofix-control-center.onrender.com",  # Your admin dashboard / frontend
        # Add any local dev URLs if needed
        "http://localhost:3000"
        "http://localhost:8080",
        "http://localhost:5173",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ────────────────────────────── DEPENDENCY ──────────────────────────────
# Make pool available to routers
def get_pool():
    return pool

# Pass pool to auth router if needed (or use dependency injection in router)
app.include_router(auth.router)