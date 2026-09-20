"""Схемы валидации и ответа для вопросов."""

from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field, TypeAdapter

QuestionText = Annotated[
    str,
    Field(
        min_length=1,
        max_length=256,
        description="Text of the question",
    ),
]

CategoryName = Annotated[
    str,
    Field(
        min_length=1,
        max_length=100,
        description="Name of the category",
    ),
]

CategoryId = Annotated[
    int,
    Field(
        gt=0,
        description="ID of the category",
    ),
]

QuestionId = Annotated[
    int,
    Field(description="ID of the question"),
]


class CategoryBase(BaseModel):
    """Общие поля схем категорий."""

    model_config = ConfigDict(
        str_strip_whitespace=True,
        extra="forbid",
    )

    name: CategoryName


class CategoryCreate(CategoryBase):
    """Контракт входных данных для создания категории."""


class CategoryRead(CategoryBase):
    """Контракт категории, возвращаемой API."""

    model_config = ConfigDict(
        from_attributes=True,
        extra="forbid",
    )

    id: CategoryId


class CategoryUpdate(CategoryBase):
    """Контракт изменения категории."""


class QuestionBase(BaseModel):
    """Общие поля схем создания, чтения и обновления вопроса."""

    model_config = ConfigDict(
        str_strip_whitespace=True,
        extra="forbid",
    )

    text: QuestionText


class QuestionCreate(QuestionBase):
    """Контракт входных данных для создания вопроса."""

    category_id: CategoryId | None = None


class QuestionRead(QuestionBase):
    """Контракт вопроса, возвращаемого API."""

    model_config = ConfigDict(
        from_attributes=True,
    )

    id: QuestionId
    category_id: CategoryId | None = None
    category: CategoryRead | None = None


class QuestionUpdate(QuestionBase):
    """Контракт полного обновления вопроса."""

    id: QuestionId
    category_id: CategoryId | None = None


CategoriesList = TypeAdapter(list[CategoryRead])
QuestionsList = TypeAdapter(list[QuestionRead])
