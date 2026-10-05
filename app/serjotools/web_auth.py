from fastapi import Cookie, Depends, HTTPException, status
from sqlalchemy.orm import Session

from .config import settings
from .database import SessionLocal
from .models import User
from .security import decode_token

COOKIE_NAME = "access_token"
LOGIN_URL = f"{settings.APP_PREFIX}/login"      # ← учитываем префикс


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def _redirect_to_login() -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_303_SEE_OTHER,
        headers={"Location": LOGIN_URL},
    )


def get_current_user_from_cookie(
    access_token: str | None = Cookie(default=None, alias=COOKIE_NAME),
    db: Session = Depends(get_db),
) -> User:
    if not access_token:
        raise _redirect_to_login()
    sub = decode_token(access_token)
    if sub is None:
        raise _redirect_to_login()
    user = db.get(User, int(sub))
    if user is None:
        raise _redirect_to_login()
    return user


def get_current_user_optional(
    access_token: str | None = Cookie(default=None, alias=COOKIE_NAME),
    db: Session = Depends(get_db),
) -> User | None:
    if not access_token:
        return None
    sub = decode_token(access_token)
    if sub is None:
        return None
    return db.get(User, int(sub))