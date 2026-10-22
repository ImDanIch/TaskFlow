from sqlalchemy import CheckConstraint, Enum, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, validates

from app.database import Base


class Task(Base):
    __tablename__ = "tasks"
    __table_args__ = (
        CheckConstraint("length(trim(title)) > 0", name="task_title_nonblank"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    title: Mapped[str] = mapped_column(String, nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(
        Enum(
            "todo", "in_progress", "done", name="task_status",
            native_enum=False, create_constraint=True, validate_strings=True,
        ),
        nullable=False, default="todo", server_default="todo",
    )
    priority: Mapped[str] = mapped_column(
        Enum(
            "low", "medium", "high", name="task_priority",
            native_enum=False, create_constraint=True, validate_strings=True,
        ),
        nullable=False, default="medium", server_default="medium",
    )

    @validates("title")
    def validate_title(self, key: str, value: str) -> str:
        if not isinstance(value, str) or not value.strip():
            raise ValueError("Task title must be a nonblank string")
        return value
