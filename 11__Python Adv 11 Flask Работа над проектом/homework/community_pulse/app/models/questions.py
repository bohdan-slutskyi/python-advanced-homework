"""Модель вопроса."""

from __future__ import annotations

from typing import TYPE_CHECKING

from app.models import db

if TYPE_CHECKING:
    from .answers import Answer, Statistic
    from .category import Category


class Question(db.Model):
    """Вопрос, на который пользователи оставляют ответы."""

    __tablename__ = "questions"

    id: db.Mapped[int] = db.mapped_column(primary_key=True)
    text: db.Mapped[str] = db.mapped_column(
        db.String(256),
        nullable=False,
    )
    category_id: db.Mapped[int | None] = db.mapped_column(
        db.ForeignKey("categories.id"),
        nullable=True,
    )
    category: db.Mapped[Category | None] = db.relationship(
        back_populates="questions",
    )
    answers: db.Mapped[list[Answer]] = db.relationship(
        back_populates="question",
        cascade="all, delete-orphan",
    )
    statistic: db.Mapped[Statistic | None] = db.relationship(
        back_populates="question",
        uselist=False,
        cascade="all, delete-orphan",
    )

    def __repr__(self) -> str:
        return f"Question: {self.text}"
