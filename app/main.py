from fastapi import FastAPI
from .database import Base, engine
from .routers import auth

Base.metadata.create_all(bind=engine)

app = FastAPI(
    title="MOTOFIX Auth Service",
    description="Secure phone + OTP login for customers and mechanics in Uganda",
    version="1.0.0"
)

app.include_router(auth.router)