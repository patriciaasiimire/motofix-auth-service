from sqlalchemy import Column, Integer, String, Boolean
from .database import Base

class User(Base):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True, index=True)
    phone = Column(String, unique=True, index=True, nullable=False)
    full_name = Column(String, nullable=True)
    role = Column(String, default="customer")  # customer / mechanic


class Request(Base):
    __tablename__ = "requests"
    id = Column(Integer, primary_key=True, index=True)
    customer_name = Column(String, nullable=False)
    service_type = Column(String, nullable=False)
    location = Column(String, nullable=False)
    description = Column(String, nullable=True)
    status = Column(String, default="pending")