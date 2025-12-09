from fastapi import FastAPI
from .database import Base, engine
from .routers import auth
from .routers import requests as requests_router

Base.metadata.create_all(bind=engine)

app = FastAPI(title="MOTOFIX Auth Service")
app.include_router(auth.router)
app.include_router(requests_router.router)