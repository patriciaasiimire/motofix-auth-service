# app/routers/auth.py

import os
import random
import logging
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
import asyncpg
from jose import jwt, JWTError

# Optional Africa's Talking SDK (fallback to console if not available)
try:
    import africastalking
except Exception:
    africastalking = None

router = APIRouter(prefix="/auth", tags=["Auth"])

# In-memory OTP store (simple & effective for MVP)
otp_store = {}

# ────────────────────────────── SCHEMAS ──────────────────────────────

class PhoneRequest(BaseModel):
    phone: str


class OTPVerify(BaseModel):
    phone: str
    otp: str
    full_name: Optional[str] = None
    role: str = "driver"  # default role


class Token(BaseModel):
    access_token: str


class UserOut(BaseModel):
    id: int
    phone: str
    full_name: str | None
    role: str


# ────────────────────────────── DEPENDENCIES ──────────────────────────────

async def get_db() -> asyncpg.Connection:
    # Reuse the same pool from main.py lifespan
    from ..main import pool  # Adjust path if needed
    async with pool.acquire() as conn:
        yield conn


# ────────────────────────────── HELPERS ──────────────────────────────

def create_jwt(data: dict) -> str:
    from ..utils import create_jwt as utils_create_jwt  # import your existing function
    return utils_create_jwt(data)


async def send_sms_via_africastalking(phone: str, message: str) -> bool:
    if africastalking is None:
        logging.debug("Africa's Talking SDK not available")
        return False

    username = os.getenv("AT_USERNAME") or os.getenv("AFRICASTALKING_USERNAME")
    api_key = os.getenv("AT_API_KEY") or os.getenv("AFRICASTALKING_APIKEY")
    from_number = os.getenv("AT_FROM") or os.getenv("AFRICASTALKING_FROM")

    if not username or not api_key:
        logging.warning("Africa's Talking credentials missing")
        return False

    try:
        africastalking.initialize(username, api_key)
        sms = africastalking.SMS
        kwargs = {"to": phone, "message": message}
        if from_number:
            kwargs["from_"] = from_number
        response = sms.send(**kwargs)
        logging.info("Africa's Talking SMS sent: %s", response)
        return True
    except Exception as e:
        logging.exception("Failed to send SMS via Africa's Talking: %s", e)
        return False


# ────────────────────────────── ENDPOINTS ──────────────────────────────

@router.post("/send-otp")
async def send_otp(req: PhoneRequest):
    otp = random.randint(100000, 999999)
    otp_store[req.phone] = str(otp)
    msg = f"Your MOTOFIX OTP is {otp}"

    sent = await send_sms_via_africastalking(req.phone, msg)

    # Always log OTP for local/dev testing
    print(f"\nOTP → {req.phone}: {otp}\n")

    if sent:
        return {"message": "OTP sent successfully"}
    else:
        return {"message": "OTP generated (printed to console - provider not configured)"}


@router.post("/login", response_model=Token)
async def login(req: OTPVerify, db: asyncpg.Connection = Depends(get_db)):
    stored_otp = otp_store.get(req.phone)
    if stored_otp != req.otp:
        raise HTTPException(status_code=400, detail="Invalid or expired OTP")

    # Check if user exists
    query = "SELECT id, phone, full_name, role FROM users WHERE phone = $1"
    user_row = await db.fetchrow(query, req.phone)

    if not user_row:
        # Create new user
        insert_query = """
            INSERT INTO users (phone, full_name, role)
            VALUES ($1, $2, $3)
            RETURNING id
        """
        user_id = await db.fetchval(insert_query, req.phone, req.full_name or "Driver", req.role)
    else:
        user_id = user_row["id"]

    # Clean up OTP
    otp_store.pop(req.phone, None)

    # Generate JWT
    token = create_jwt({"sub": str(user_id), "role": req.role or "driver"})
    return {"access_token": token}


@router.get("/me", response_model=UserOut)
async def me(token: str = Depends(oauth2_scheme), db: asyncpg.Connection = Depends(get_db)):
    secret_key = os.getenv("SECRET_KEY")
    algorithm = os.getenv("ALGORITHM", "HS256")

    try:
        payload = jwt.decode(token, secret_key, algorithms=[algorithm])
        user_id: str = payload.get("sub")
        if user_id is None:
            raise HTTPException(status_code=401, detail="Invalid token")
    except JWTError:
        raise HTTPException(status_code=401, detail="Invalid token")

    query = "SELECT id, phone, full_name, role FROM users WHERE id = $1"
    user_row = await db.fetchrow(query, int(user_id))
    if not user_row:
        raise HTTPException(status_code=404, detail="User not found")

    return dict(user_row)