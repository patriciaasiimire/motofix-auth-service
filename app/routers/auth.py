# app/routers/auth.py

import os
import random
import logging
from fastapi import APIRouter, Depends, HTTPException, status, Request, Response
from fastapi.security import OAuth2PasswordBearer
from pydantic import BaseModel
from typing import Optional
import asyncpg
from jose import jwt, JWTError

# Optional Africa's Talking SDK (fallback to console if not available)
try:
    import africastalking
except Exception:
    africastalking = None

router = APIRouter(prefix="/auth", tags=["Auth"])

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/login")

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
    from ..main import pool  # Reuse pool from main.py
    async with pool.acquire() as conn:
        yield conn


# ────────────────────────────── HELPERS ──────────────────────────────

def create_jwt(data: dict) -> str:
    from ..utils import create_jwt as utils_create_jwt
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

        # Correct Africa's Talking SDK call: message first, recipients list second
        recipients = [phone]
        if from_number:
            response = sms.send(message, recipients, sender=from_number)
        else:
            response = sms.send(message, recipients)

        logging.info("Africa's Talking SMS sent successfully: %s", response)
        return True

    except Exception as e:
        logging.exception("Failed to send SMS via Africa's Talking: %s", e)
        return False


# ────────────────────────────── ENDPOINTS ──────────────────────────────

@router.post("/send-otp")
async def send_otp(req: PhoneRequest):
    phone = req.phone.strip()

    # Basic Ugandan phone validation: +256 followed by 9 digits (e.g. +256712345678)
    if not phone.startswith("+256") or len(phone) != 13 or not phone[4:].isdigit():
        raise HTTPException(status_code=422, detail="Invalid phone format. Use +256XXXXXXXXX")

    otp = f"{random.randint(0, 999999):06d}"
    otp_store[phone] = otp
    msg = f"Your MOTOFIX OTP is {otp}. Valid for 10 minutes."

    sent = await send_sms_via_africastalking(phone, msg)

    # Always print/log OTP to console for testing (remove in production)
    logging.info("OTP for %s: %s", phone, otp)
    print(f"\nOTP → {phone}: {otp}\n")

    # For development/testing return the OTP in the response
    return {"message": "OTP sent successfully", "otp": otp}


@router.post("/login", response_model=Token)
async def login(req: OTPVerify, response: Response, db: asyncpg.Connection = Depends(get_db)):
    logging.info(f"🔐 [POST /auth/login] Login attempt for phone: {req.phone}")
    
    stored_otp = otp_store.get(req.phone)
    if stored_otp != req.otp:
        logging.warning(f"❌ [POST /auth/login] Invalid OTP for phone: {req.phone}")
        raise HTTPException(status_code=400, detail="Invalid or expired OTP")

    # Check if user exists
    query = "SELECT id, phone, full_name, role FROM users WHERE phone = $1"
    user_row = await db.fetchrow(query, req.phone)

    if not user_row:
        # Create new user
        logging.info(f"✅ [POST /auth/login] Creating new user: {req.phone}")
        insert_query = """
            INSERT INTO users (phone, full_name, role)
            VALUES ($1, $2, $3)
            RETURNING id
        """
        user_id = await db.fetchval(
            insert_query,
            req.phone,
            req.full_name or "Driver",
            req.role
        )
    else:
        logging.info(f"ℹ️ [POST /auth/login] Existing user found: {req.phone}")
        user_id = user_row["id"]

    # Clean up OTP
    otp_store.pop(req.phone, None)

    # Generate JWT
    token = create_jwt({"sub": str(user_id), "role": req.role or "driver"})
    logging.debug(f"✅ [POST /auth/login] JWT created for user_id: {user_id}")

    # Fetch user record to return in response
    user_row = await db.fetchrow("SELECT id, phone, full_name, role FROM users WHERE id = $1", int(user_id))

    # Set token as a secure httpOnly cookie so the frontend can persist authentication
    # Cookie lifetime is aligned with JWT expiry (default ~30 days). Adjust via env if needed.
    cookie_max_age = int(os.getenv("ACCESS_TOKEN_EXPIRE_SECONDS", 60 * 60 * 24 * 30))
    secure_cookie = os.getenv("ENV", "production") == "production"
    response.set_cookie(
        key="access_token",
        value=token,
        httponly=True,
        secure=secure_cookie,
        samesite="lax",
        max_age=cookie_max_age,
        path="/",
    )
    logging.info(f"✅ [POST /auth/login] Login successful for phone: {req.phone}, token issued")

    return {"access_token": token, "user": dict(user_row) if user_row else None}


async def _get_user_from_token(token: str, db: asyncpg.Connection):
    secret_key = os.getenv("SECRET_KEY")
    algorithm = os.getenv("ALGORITHM", "HS256")

    logging.debug(f"🔐 [Token Decode] Using algorithm: {algorithm}")

    try:
        payload = jwt.decode(token, secret_key, algorithms=[algorithm])
        user_id: str = payload.get("sub")
        logging.debug(f"✅ [Token Decode] Successfully decoded token for user_id: {user_id}")
        if not user_id:
            logging.error("❌ [Token Decode] Token missing 'sub' claim")
            raise HTTPException(status_code=401, detail="Invalid token")
    except JWTError as e:
        logging.error(f"❌ [Token Decode] JWT decode failed: {str(e)}")
        raise HTTPException(status_code=401, detail="Invalid token")

    query = "SELECT id, phone, full_name, role FROM users WHERE id = $1"
    logging.debug(f"🔍 [DB Query] Looking up user with id={user_id}")
    user_row = await db.fetchrow(query, int(user_id))
    if not user_row:
        logging.error(f"❌ [DB Query] User not found with id={user_id}")
        raise HTTPException(status_code=404, detail="User not found")

    logging.info(f"✅ [Auth] User verified successfully: {user_row.get('phone')}")
    return dict(user_row)


async def get_current_user(request: Request, db: asyncpg.Connection = Depends(get_db)):
    # Prefer Authorization header, fallback to httpOnly cookie named 'access_token'
    token = None
    auth_header = request.headers.get("authorization")
    request_origin = request.headers.get("origin", "unknown")
    
    logging.info(f"🔍 [get_current_user] Origin: {request_origin}")
    logging.debug(f"📋 [get_current_user] Headers: Authorization={bool(auth_header)}")
    
    if auth_header and auth_header.lower().startswith("bearer "):
        token = auth_header.split(" ", 1)[1].strip()
        logging.debug(f"✅ [get_current_user] Bearer token found in Authorization header (length={len(token)})")
    else:
        token = request.cookies.get("access_token")
        if token:
            logging.debug(f"ℹ️ [get_current_user] Using token from httpOnly cookie")
        else:
            logging.debug(f"ℹ️ [get_current_user] No Authorization header, no cookie")

    if not token:
        logging.error("❌ [get_current_user] No token found in request")
        raise HTTPException(status_code=401, detail="Not authenticated")

    logging.debug(f"🔐 [get_current_user] Verifying token...")
    return await _get_user_from_token(token, db)


@router.get("/me", response_model=UserOut)
async def me(user: dict = Depends(get_current_user)):
    logging.info(f"✅ [GET /auth/me] Successfully verified user: {user.get('phone')}")
    return user


@router.post("/logout")
async def logout(response: Response):
    # Clear the access_token cookie
    response.delete_cookie(key="access_token", path="/")
    return {"message": "Logged out"}