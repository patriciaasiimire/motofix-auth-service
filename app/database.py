from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
import os
import logging

try:
    from dotenv import load_dotenv
except ImportError:
    # Provide a no-op fallback so the rest of the module can import fine
    def load_dotenv(*args, **kwargs):
        logging.warning("python-dotenv not installed; skipping load_dotenv()")

load_dotenv()
DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./auth.db")
engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()