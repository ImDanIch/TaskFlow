from pathlib import Path

from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, sessionmaker


DATABASE_PATH = Path(__file__).resolve().parent.parent / "taskflow.db"
engine = create_engine(
    f"sqlite:///{DATABASE_PATH.as_posix()}",
    connect_args={"check_same_thread": False},
)
SessionLocal = sessionmaker(bind=engine)


def get_session():
    with SessionLocal() as session:
        yield session


class Base(DeclarativeBase):
    pass


def initialize_database() -> None:
    # Register models with Base before creating their tables.
    from app import models  # noqa: F401

    Base.metadata.create_all(bind=engine)
