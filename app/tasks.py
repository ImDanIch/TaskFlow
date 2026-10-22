from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Response
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database import get_session
from app.models import Task
from app.schemas import TaskCreate, TaskPriority, TaskResponse, TaskStatus, TaskUpdate


router = APIRouter(prefix="/tasks", tags=["tasks"])
DatabaseSession = Annotated[Session, Depends(get_session)]


def get_task_or_404(task_id: int, session: Session) -> Task:
    task = session.get(Task, task_id)
    if task is None:
        raise HTTPException(status_code=404, detail="Task not found")
    return task


@router.post("", response_model=TaskResponse, status_code=201)
def create_task(data: TaskCreate, session: DatabaseSession):
    task = Task(**data.model_dump())
    session.add(task)
    session.commit()
    session.refresh(task)
    return task


@router.get("", response_model=list[TaskResponse])
def list_tasks(
    session: DatabaseSession,
    status: TaskStatus | None = None,
    priority: TaskPriority | None = None,
):
    query = select(Task).order_by(Task.id)
    if status is not None:
        query = query.where(Task.status == status)
    if priority is not None:
        query = query.where(Task.priority == priority)
    return session.scalars(query).all()


@router.get("/{task_id}", response_model=TaskResponse)
def retrieve_task(task_id: int, session: DatabaseSession):
    return get_task_or_404(task_id, session)


@router.patch("/{task_id}", response_model=TaskResponse)
def update_task(task_id: int, data: TaskUpdate, session: DatabaseSession):
    task = get_task_or_404(task_id, session)
    for field, value in data.model_dump(exclude_unset=True).items():
        setattr(task, field, value)
    session.commit()
    session.refresh(task)
    return task


@router.delete("/{task_id}", status_code=204)
def delete_task(task_id: int, session: DatabaseSession):
    task = get_task_or_404(task_id, session)
    session.delete(task)
    session.commit()
    return Response(status_code=204)
