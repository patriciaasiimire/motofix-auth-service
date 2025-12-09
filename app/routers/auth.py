from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.orm import Session
from .. import models, schemas
from ..database import get_db
from ..utils import create_jwt
import random

router = APIRouter(prefix="/auth", tags=["Auth"])
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/login")

# Fake OTP store
otp_store = {}

@router.post("/send-otp")
def send_otp(req: schemas.PhoneRequest):
    otp = random.randint(100000, 999999)
    otp_store[req.phone] = str(otp)
    print(f"\nOTP → {req.phone}: {otp}\n")
    return {"message": "OTP sent"}

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