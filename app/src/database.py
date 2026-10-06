from sqlalchemy import create_engine, MetaData
from sqlalchemy.orm import sessionmaker, DeclarativeBase

from .config import settings

# engine = create_engine(settings.DATABASE_URL, echo=False, future=True)
engine = create_engine(
    settings.DATABASE_URL,
    echo=False,
    future=True,
    pool_pre_ping=True,      # проверяет соединение перед использованием
    pool_recycle=300,        # закрывает соединения старше 5 минут
)


SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)


class Base(DeclarativeBase):
    metadata = MetaData(schema=settings.DB_SCHEMA)