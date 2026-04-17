"""Configuração de banco de dados SQLAlchemy e dependência de sessão."""

from collections.abc import Generator

from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from app.core.settings import settings


class Base(DeclarativeBase):
    """Classe base para modelos ORM SQLAlchemy."""


connect_args = {"check_same_thread": False} if settings.database_url.startswith("sqlite") else {}

engine = create_engine(settings.database_url, connect_args=connect_args, future=True)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, expire_on_commit=False, class_=Session)


def get_db() -> Generator[Session, None, None]:
    """Dependência FastAPI que fornece uma sessão DB com escopo de transação."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
