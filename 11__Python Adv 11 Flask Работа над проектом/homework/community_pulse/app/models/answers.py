"""Модель Answer и агрегированная статистика."""

from __future__ import annotations

from typing import TYPE_CHECKING

from app.models import db

if TYPE_CHECKING:
    from .questions import Question


class Answer(db.Model):
    """Один ответ пользователя на вопрос."""

    __tablename__ = "answers"

    id: db.Mapped[int] = db.mapped_column(primary_key=True)
    question_id: db.Mapped[int] = db.mapped_column(
        db.ForeignKey("questions.id"),
        nullable=False,
    )
    is_agree: db.Mapped[bool] = db.mapped_column(
        db.Boolean,
        nullable=False,
    )
    question: db.Mapped[Question] = db.relationship(
        back_populates="answers",
    )

    def __repr__(self) -> str:
        return f"Answer: question_id={self.question_id}, is_agree={self.is_agree}"


class Statistic(db.Model):
    """Счётчики согласных и несогласных ответов по вопросу."""

    __tablename__ = "statistics"

    question_id: db.Mapped[int] = db.mapped_column(
        db.ForeignKey("questions.id"),
        primary_key=True,
    )
    agree_count: db.Mapped[int] = db.mapped_column(
        db.Integer,
        nullable=False,
        default=0,
    )
    disagree_count: db.Mapped[int] = db.mapped_column(
        db.Integer,
        nullable=False,
        default=0,
    )
    question: db.Mapped[Question] = db.relationship(
        back_populates="statistic",
    )

    def __repr__(self) -> str:
        return (
            f"Statistic: question_id={self.question_id}, "
            f"agree={self.agree_count}, disagree={self.disagree_count}"
        )
