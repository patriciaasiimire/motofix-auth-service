from pydantic import BaseModel
from typing import Optional

class PhoneRequest(BaseModel):
    phone: str

class OTPVerify(BaseModel):
    phone: str
    otp: str
    full_name: Optional[str] = None
    role: str = "customer"

class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"

class UserOut(BaseModel):
    id: int
    phone: str
    full_name: Optional[str]
    role: str

    class Config:
        from_attributes = True


class RequestCreate(BaseModel):
    customer_name: str
    service_type: str
    location: str
    description: Optional[str] = None


class RequestOut(BaseModel):
    id: int
    customer_name: str
    service_type: str
    location: str
    description: Optional[str]
    status: str

    class Config:
        from_attributes = True