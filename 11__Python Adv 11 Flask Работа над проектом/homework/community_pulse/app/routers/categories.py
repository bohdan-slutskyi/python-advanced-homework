"""Эндпоинты для работы с категориями вопросов."""

from __future__ import annotations

from flask import Blueprint, jsonify, request
from pydantic import ValidationError
from sqlalchemy import select

from app.models import Category, db
from app.schemas.questions import (
    CategoriesList,
    CategoryCreate,
    CategoryRead,
    CategoryUpdate,
)

categories_bp = Blueprint("categories", __name__, url_prefix="/categories")


def _category_data(category: Category) -> dict[str, object]:
    """Преобразует объект категории в JSON-совместимый словарь."""

    return CategoryRead.model_validate(category).model_dump()


def _validation_error(error: ValidationError):
    """Возвращает единый ответ API для ошибки схемы."""

    return jsonify({"errors": error.errors()}), 400


def _get_category_or_404(category_id: int):
    """Возвращает категорию или ответ 404."""

    category = db.session.get(Category, category_id)
    if category is None:
        return None, (
            jsonify({"message": "Категория с таким ID не найдена"}),
            404,
        )

    return category, None


@categories_bp.route("", methods=["GET"], strict_slashes=False)
def get_categories():
    """Получение списка всех категорий."""

    categories = db.session.scalars(
        select(Category).order_by(Category.id)
    ).all()
    result = CategoriesList.dump_python(
        CategoriesList.validate_python(categories)
    )
    return jsonify(result), 200


@categories_bp.route("", methods=["POST"], strict_slashes=False)
def create_category():
    """Создание новой категории."""

    try:
        payload = CategoryCreate.model_validate(
            request.get_json(silent=True)
        )
    except ValidationError as error:
        return _validation_error(error)

    category = Category(name=payload.name)
    db.session.add(category)
    db.session.commit()

    return jsonify(_category_data(category)), 201


@categories_bp.route("/<int:id>", methods=["GET"])
def get_category(id: int):
    """Получение категории по ID."""

    category, error = _get_category_or_404(id)
    if error:
        return error

    return jsonify(_category_data(category)), 200


@categories_bp.route("/<int:id>", methods=["PUT"])
def update_category(id: int):
    """Обновление категории по ID."""

    category, error = _get_category_or_404(id)
    if error:
        return error

    try:
        payload = CategoryUpdate.model_validate(
            request.get_json(silent=True)
        )
    except ValidationError as error:
        return _validation_error(error)

    category.name = payload.name
    db.session.commit()

    return jsonify(_category_data(category)), 200


@categories_bp.route("/<int:id>", methods=["DELETE"])
def delete_category(id: int):
    """Удаление категории по ID."""

    category, error = _get_category_or_404(id)
    if error:
        return error

    db.session.delete(category)
    db.session.commit()

    return jsonify({"message": f"Категория с ID {id} удалена"}), 200
