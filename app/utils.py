from datetime import datetime, timedelta
import os
import logging

try:
    from jose import jwt
except ImportError:
    # Provide a clear fallback that raises at runtime if used.
    class _MissingJWT:
        def encode(self, *args, **kwargs):
            raise ImportError("python-jose is not installed; install python-jose to use JWT features")

    jwt = _MissingJWT()

try:
    from dotenv import load_dotenv
except ImportError:
    def load_dotenv(*args, **kwargs):
        logging.warning("python-dotenv not installed; skipping load_dotenv()")

load_dotenv()

def create_jwt(data: dict, expires_minutes: int = 43200) -> str:
    to_encode = data.copy()
    expire = datetime.utcnow() + timedelta(minutes=expires_minutes)
    to_encode.update({"exp": expire})
    secret = os.getenv("SECRET_KEY")
    algorithm = os.getenv("ALGORITHM", "HS256")
    return jwt.encode(to_encode, secret, algorithm=algorithm)