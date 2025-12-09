from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.orm import Session
from .. import models, schemas
from ..database import get_db
from ..utils import create_jwt
import random
import os
import logging

# Optional Africa's Talking SDK. If not installed or not configured, we fall back
# to printing the OTP to console (development mode).
try:
    import africastalking
except Exception:  # keep broad to catch ImportError or other issues
    africastalking = None

router = APIRouter(prefix="/auth", tags=["Auth"])
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/login")

# Fake OTP store
otp_store = {}

@router.post("/send-otp")
def send_otp(req: schemas.PhoneRequest):
    otp = random.randint(100000, 999999)
    otp_store[req.phone] = str(otp)
    # Attempt to send via Africa's Talking when configured
    msg = f"Your MOTOFIX OTP is {otp}"

    def _send_via_africastalking(phone: str, message: str) -> bool:
        if africastalking is None:
            logging.debug("africastalking SDK not available; skipping provider send")
            return False

        username = os.getenv("AT_USERNAME") or os.getenv("AFRICASTALKING_USERNAME")
        api_key = os.getenv("AT_API_KEY") or os.getenv("AFRICASTALKING_APIKEY")
        from_number = os.getenv("AT_FROM") or os.getenv("AFRICASTALKING_FROM")

        if not username or not api_key:
            logging.warning("Africa's Talking credentials not set; skipping send")
            return False

        try:
            africastalking.initialize(username, api_key)
            sms = africastalking.SMS
            # `from_` is optional depending on your AT settings
            params = {"to": phone, "message": message}
            if from_number:
                # the africastalking SDK `send` signature varies; use keyword 'from_' when available
                try:
                    response = sms.send(message, [phone], from_=from_number)
                except TypeError:
                    response = sms.send(message, [phone])
            else:
                response = sms.send(message, [phone])
            logging.info("Africa's Talking SMS response: %s", response)
            return True
        except Exception:
            logging.exception("Failed to send SMS via Africa's Talking")
            return False

    sent = _send_via_africastalking(req.phone, msg)

    # Always print OTP to console in dev for convenience (and as fallback)
    print(f"\nOTP → {req.phone}: {otp}\n")

    if sent:
        return {"message": "OTP sent via Africa's Talking"}
    else:
        return {"message": "OTP stored and printed (provider not configured)"}

@router.post("/login", response_model=schemas.Token)
def login(req: schemas.OTPVerify, db: Session = Depends(get_db)):
    if otp_store.get(req.phone) != req.otp:
        raise HTTPException(status_code=400, detail="Wrong OTP")
    
    user = db.query(models.User).filter(models.User.phone == req.phone).first()
    if not user:
        user = models.User(phone=req.phone, full_name=req.full_name, role=req.role)
        db.add(user)
        db.commit()
        db.refresh(user)
    
    del otp_store[req.phone]
    
    token = create_jwt({"sub": str(user.id), "role": user.role})
    return {"access_token": token}

@router.get("/me", response_model=schemas.UserOut)
def me(token: str = Depends(oauth2_scheme), db: Session = Depends(get_db)):
    from jose import jwt, JWTError
    try:
        payload = jwt.decode(token, os.getenv("SECRET_KEY"), algorithms=[os.getenv("ALGORITHM")])
        user_id: str = payload.get("sub")
    except JWTError:
        raise HTTPException(status_code=401, detail="Invalid token")
    
    user = db.query(models.User).filter(models.User.id == int(user_id)).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    return user