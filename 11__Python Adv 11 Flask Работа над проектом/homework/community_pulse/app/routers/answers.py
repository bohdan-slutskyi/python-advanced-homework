"""Эндпоинты для Answer и статистики."""

from __future__ import annotations

from flask import Blueprint, jsonify, request
from pydantic import ValidationError
from sqlalchemy import select

from app.models import Answer, Question, Statistic, db
from app.schemas.answers import AnswerCreate, AnswerRead, StatisticsList

answers_bp = Blueprint("answers", __name__, url_prefix="/answers")


@answers_bp.route("", methods=["GET"], strict_slashes=False)
def get_answers():
    """Получение агрегированной статистики ответов."""

    statistics = db.session.scalars(
        select(Statistic).order_by(Statistic.question_id)
    ).all()
    results = StatisticsList.dump_python(StatisticsList.validate_python(statistics))
    return jsonify(results), 200


@answers_bp.route("", methods=["POST"], strict_slashes=False)
def add_answer():
    """Добавление ответа на вопрос с обновлением статистики."""

    try:
        payload = AnswerCreate.model_validate(request.get_json(silent=True))
    except ValidationError as error:
        return jsonify({"errors": error.errors()}), 400

    question = db.session.get(Question, payload.question_id)
    if question is None:
        return jsonify({"message": "Вопрос не найден"}), 404

    answer = Answer(
        question_id=question.id,
        is_agree=payload.is_agree,
    )
    db.session.add(answer)

    statistic = db.session.scalar(
        select(Statistic).where(Statistic.question_id == question.id)
    )
    if statistic is None:
        statistic = Statistic(
            question_id=question.id,
            agree_count=0,
            disagree_count=0,
        )
        db.session.add(statistic)

    if payload.is_agree:
        statistic.agree_count += 1
    else:
        statistic.disagree_count += 1

    db.session.commit()
    result = AnswerRead.model_validate(answer).model_dump()
    return jsonify(
        {
            "message": f"Ответ на вопрос {question.id} добавлен",
            "answer": result,
        }
    ), 201
