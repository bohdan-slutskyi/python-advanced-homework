"""Эндпоинты для работы с вопросами."""

from __future__ import annotations

from flask import Blueprint, jsonify, request
from pydantic import ValidationError
from sqlalchemy import select

from app.models import Category, Question, db
from app.schemas.questions import (
    QuestionCreate,
    QuestionRead,
    QuestionsList,
    QuestionUpdate,
)

questions_bp = Blueprint("questions", __name__, url_prefix="/questions")


def _question_data(question: Question) -> dict[str, object]:
    """Преобразует объект вопроса в JSON-совместимый словарь."""

    return QuestionRead.model_validate(question).model_dump()


def _category_or_404(category_id: int):
    """Возвращает категорию или ответ 404."""

    category = db.session.get(Category, category_id)
    if category is None:
        return None, (
            jsonify({"message": "Категория с таким ID не найдена"}),
            404,
        )

    return category, None


def _validation_error(error: ValidationError):
    """Возвращает единый ответ API для ошибки схемы."""

    return jsonify({"errors": error.errors()}), 400


@questions_bp.route("", methods=["GET"], strict_slashes=False)
def get_questions():
    """Получение списка всех вопросов."""

    questions = db.session.scalars(select(Question).order_by(Question.id)).all()
    result = QuestionsList.dump_python(QuestionsList.validate_python(questions))
    return jsonify(result), 200


@questions_bp.route("", methods=["POST"], strict_slashes=False)
def create_question():
    """Создание нового вопроса."""

    try:
        payload = QuestionCreate.model_validate(request.get_json(silent=True))
    except ValidationError as error:
        return _validation_error(error)

    category = None
    if payload.category_id is not None:
        category, error = _category_or_404(payload.category_id)
        if error:
            return error

    question = Question(text=payload.text, category=category)
    db.session.add(question)
    db.session.commit()

    return jsonify(_question_data(question)), 201


@questions_bp.route("/<int:id>", methods=["GET"])
def get_question(id: int):
    """Получение деталей конкретного вопроса по его ID."""

    question = db.session.get(Question, id)
    if question is None:
        return jsonify({"message": "Вопрос с таким ID не найден"}), 404

    return jsonify(_question_data(question)), 200


@questions_bp.route("/<int:id>", methods=["PUT"])
def update_question(id: int):
    """Обновление конкретного вопроса по его ID."""

    question = db.session.get(Question, id)
    if question is None:
        return jsonify({"message": "Вопрос с таким ID не найден"}), 404

    data = request.get_json(silent=True)
    if isinstance(data, dict) and "id" not in data:
        data = {**data, "id": id}

    try:
        payload = QuestionUpdate.model_validate(data)
    except ValidationError as error:
        return _validation_error(error)

    if payload.id != id:
        return jsonify({"message": "ID вопроса в URL и теле не совпадают"}), 400

    if isinstance(data, dict) and "category_id" in data:
        if payload.category_id is None:
            question.category = None
        else:
            category, error = _category_or_404(payload.category_id)
            if error:
                return error
            question.category = category

    question.text = payload.text
    db.session.commit()
    return jsonify(_question_data(question)), 200


@questions_bp.route("/<int:id>", methods=["DELETE"])
def delete_question(id: int):
    """Удаление конкретного вопроса по его ID."""

    question = db.session.get(Question, id)
    if question is None:
        return jsonify({"message": "Вопрос с таким ID не найден"}), 404

    db.session.delete(question)
    db.session.commit()
    return jsonify({"message": f"Вопрос с ID {id} удален"}), 200
