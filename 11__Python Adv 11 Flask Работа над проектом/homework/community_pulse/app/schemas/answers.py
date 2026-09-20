"""Схемы валидации ответов и статистики."""

from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field, TypeAdapter

AnswerId = Annotated[
    int,
    Field(description="ID of the answer"),
]
QuestionId = Annotated[
    int,
    Field(gt=0, description="ID of the question"),
]


class AnswerBase(BaseModel):
    """Общие поля схем ответа."""

    model_config = ConfigDict(extra="forbid")

    question_id: QuestionId
    is_agree: bool = Field(description="Whether the answer is agree")


class AnswerCreate(AnswerBase):
    """Контракт входных данных для ответа на вопрос."""


class AnswerRead(AnswerBase):
    """Контракт одного сохранённого ответа."""

    model_config = ConfigDict(from_attributes=True)

    id: AnswerId


class StatisticRead(BaseModel):
    """Контракт агрегированной статистики по вопросу."""

    model_config = ConfigDict(from_attributes=True)

    question_id: int
    agree_count: int
    disagree_count: int


AnswersList = TypeAdapter(list[AnswerRead])
StatisticsList = TypeAdapter(list[StatisticRead])
