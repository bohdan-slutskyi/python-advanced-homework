"""Pydantic-схемы API Community Pulse."""

from app.schemas.answers import (
    AnswerCreate,
    AnswerRead,
    AnswersList,
    StatisticRead,
    StatisticsList,
)
from app.schemas.questions import (
    CategoriesList,
    CategoryBase,
    CategoryCreate,
    CategoryRead,
    CategoryUpdate,
    QuestionBase,
    QuestionCreate,
    QuestionRead,
    QuestionsList,
    QuestionUpdate,
)

__all__ = [
    "AnswerCreate",
    "AnswerRead",
    "AnswersList",
    "CategoryBase",
    "CategoryCreate",
    "CategoryRead",
    "CategoryUpdate",
    "CategoriesList",
    "QuestionBase",
    "QuestionCreate",
    "QuestionRead",
    "QuestionUpdate",
    "QuestionsList",
    "StatisticRead",
    "StatisticsList",
]
