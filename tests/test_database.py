import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, inspect, select
from sqlalchemy.exc import IntegrityError, StatementError
from sqlalchemy.orm import Session

from app import database
from app.main import app
from app.models import Task


def test_startup_initializes_database(database_engine):
    assert not inspect(database_engine).has_table("tasks")
    with TestClient(app):
        assert inspect(database_engine).has_table("tasks")
    # Starting again is safe with an existing database.
    with TestClient(app):
        assert inspect(database_engine).has_table("tasks")


def test_task_persists_after_engine_restart(database_engine):
    database.initialize_database()
    with database.SessionLocal() as session:
        task = Task(title="Study SQLAlchemy", description="Practice persistence")
        session.add(task)
        session.commit()
        task_id = task.id
    url = database_engine.url
    database_engine.dispose()

    restarted_engine = create_engine(url)
    try:
        with Session(restarted_engine) as session:
            saved = session.get(Task, task_id)
            assert saved is not None
            assert saved.title == "Study SQLAlchemy"
            assert saved.description == "Practice persistence"
            assert saved.status == "todo"
            assert saved.priority == "medium"
    finally:
        restarted_engine.dispose()


@pytest.mark.parametrize("status", ["todo", "in_progress", "done"])
@pytest.mark.parametrize("priority", ["low", "medium", "high"])
def test_allowed_values(database_engine, status, priority):
    database.initialize_database()
    with database.SessionLocal() as session:
        session.add(Task(title="Learn", status=status, priority=priority))
        session.commit()
        task = session.scalar(select(Task))
        assert (task.status, task.priority, task.description) == (status, priority, None)


@pytest.mark.parametrize("title", [None, "", "   ", "\t\n"])
def test_rejects_blank_titles(title):
    with pytest.raises(ValueError, match="nonblank"):
        Task(title=title)


@pytest.mark.parametrize("field", ["status", "priority"])
def test_rejects_invalid_enum_values(database_engine, field):
    database.initialize_database()
    with database.SessionLocal() as session:
        session.add(Task(title="Learn", **{field: "invalid"}))
        with pytest.raises(StatementError):
            session.commit()


@pytest.mark.parametrize("title", [None, "", "   "])
def test_database_enforces_title_constraint(database_engine, title):
    database.initialize_database()
    with database_engine.begin() as connection:
        with pytest.raises(IntegrityError):
            connection.execute(Task.__table__.insert().values(title=title))
