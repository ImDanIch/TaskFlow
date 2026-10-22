import pytest
from sqlalchemy import create_engine

from app import database


@pytest.fixture(autouse=True)
def database_engine(tmp_path, monkeypatch):
    engine = create_engine(
        f"sqlite:///{(tmp_path / 'test.db').as_posix()}",
        connect_args={"check_same_thread": False},
    )
    monkeypatch.setattr(database, "engine", engine)
    monkeypatch.setattr(database, "SessionLocal", database.sessionmaker(bind=engine))
    yield engine
    engine.dispose()
