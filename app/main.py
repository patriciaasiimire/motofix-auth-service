from fastapi import FastAPI
from .database import Base, engine
from .routers import auth
Base.metadata.create_all(bind=engine)

app = FastAPI(title="MOTOFIX Auth Service")
app.include_router(auth.router)