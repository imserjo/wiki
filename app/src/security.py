from datetime import datetime, timedelta, timezone

import bcrypt
from jose import jwt, JWTError

from .config import settings


# ---------- Пароли (bcrypt напрямую) ----------

def _to_72_bytes(password: str) -> bytes:
    """bcrypt принимает максимум 72 байта — обрезаем аккуратно."""
    pwd_bytes = password.encode("utf-8")
    return pwd_bytes[:72]


def hash_password(password: str) -> str:
    hashed = bcrypt.hashpw(_to_72_bytes(password), bcrypt.gensalt())
    return hashed.decode("utf-8")


def verify_password(plain: str, hashed: str) -> bool:
    try:
        return bcrypt.checkpw(_to_72_bytes(plain), hashed.encode("utf-8"))
    except (ValueError, TypeError):
        return False


# ---------- JWT (python-jose) ----------

def create_access_token(subject: str | int, expires_minutes: int | None = None) -> str:
    expire = datetime.now(timezone.utc) + timedelta(
        minutes=expires_minutes or settings.ACCESS_TOKEN_EXPIRE_MINUTES
    )
    payload = {"sub": str(subject), "exp": expire}
    return jwt.encode(payload, settings.SECRET_KEY, algorithm=settings.ALGORITHM)


def decode_token(token: str) -> str | None:
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
        return payload.get("sub")
    except JWTError:
        return None