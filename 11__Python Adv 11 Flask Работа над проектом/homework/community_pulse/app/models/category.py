"""Модель категории вопросов."""

from __future__ import annotations

from typing import TYPE_CHECKING

from app.models import db

if TYPE_CHECKING:
    from .questions import Question


class Category(db.Model):
    """Категория, к которой можно отнести вопросы."""

    __tablename__ = "categories"

    id: db.Mapped[int] = db.mapped_column(
        primary_key=True,
        autoincrement=True,
    )
    name: db.Mapped[str] = db.mapped_column(
        db.String(100),
        nullable=False,
    )
    questions: db.Mapped[list[Question]] = db.relationship(
        back_populates="category",
    )

    def __init__(self, name: str) -> None:
        normalized_name = name.strip()
        if not normalized_name:
            raise ValueError("Название категории не может быть пустым")
        self.name = normalized_name

    def __repr__(self) -> str:
        return f"Category: {self.name}"
