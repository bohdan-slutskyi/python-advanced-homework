"""ДЗ №5."""

# Требуется: Python 3.12+ и зависимости Flask, Flask-SQLAlchemy, Flask-Migrate, SQLAlchemy.
# Запуск из этой папки:
# uv run --no-project --python 3.12 --with "Flask>=3.1,<4" --with "Flask-SQLAlchemy>=3.1,<4" --with "Flask-Migrate>=4,<5" --with "SQLAlchemy>=2,<3" python homework_05.py
#
# Если uv не установлен:
# python3.12 -m venv .venv
# source .venv/bin/activate
# python -m pip install "Flask>=3.1,<4" "Flask-SQLAlchemy>=3.1,<4" "Flask-Migrate>=4,<5" "SQLAlchemy>=2,<3"
# python homework_05.py

from __future__ import annotations

import os
import tempfile
from pathlib import Path

from flask import Flask
from flask_migrate import Migrate
from flask_sqlalchemy import SQLAlchemy


db = SQLAlchemy()
migrate = Migrate()

_DEFAULT_DATABASE_PATH = (
    Path(tempfile.gettempdir()) / "python_advanced_homework_05.sqlite3"
)


class Category(db.Model):
    __tablename__ = "categories"

    id: db.Mapped[int] = db.mapped_column(
        primary_key=True,
        autoincrement=True,
    )
    name: db.Mapped[str] = db.mapped_column(
        db.String(100),
        nullable=False,
    )
    questions: db.Mapped[list["Question"]] = db.relationship(
        back_populates="category"
    )

    def __init__(self, name: str) -> None:
        normalized_name = name.strip()
        if not normalized_name:
            raise ValueError("Название категории не может быть пустым")
        self.name = normalized_name


class Question(db.Model):
    __tablename__ = "questions"

    id: db.Mapped[int] = db.mapped_column(primary_key=True)
    text: db.Mapped[str] = db.mapped_column(db.String(255), nullable=False)
    category_id: db.Mapped[int | None] = db.mapped_column(
        db.ForeignKey("categories.id"),
        nullable=True,
    )
    category: db.Mapped["Category"] = db.relationship(
        back_populates="questions"
    )
    responses: db.Mapped[list["Answer"]] = db.relationship(
        back_populates="question",
        cascade="all, delete-orphan",
    )


class Answer(db.Model):
    __tablename__ = "answers"

    id: db.Mapped[int] = db.mapped_column(primary_key=True)
    question_id: db.Mapped[int] = db.mapped_column(
        db.ForeignKey("questions.id"),
        nullable=False,
    )
    is_agree: db.Mapped[bool] = db.mapped_column(nullable=False)
    question: db.Mapped["Question"] = db.relationship(
        back_populates="responses"
    )


def create_app(database_url: str | None = None) -> Flask:
    """Создаёт приложение с моделями и подключённым Flask-Migrate."""

    app = Flask(__name__)
    configured_database_url = database_url or os.environ.get(
        "DATABASE_URL",
        f"sqlite:///{_DEFAULT_DATABASE_PATH}",
    )
    app.config.from_mapping(
        SECRET_KEY="homework-05",
        SQLALCHEMY_DATABASE_URI=configured_database_url,
        SQLALCHEMY_TRACK_MODIFICATIONS=False,
    )
    db.init_app(app)
    migrate.init_app(app, db)
    return app


def run_smoke_check() -> None:
    """Проверяет новую модель и обе стороны существующих связей."""

    smoke_app = create_app("sqlite:///:memory:")
    with smoke_app.app_context():
        db.create_all()
        try:
            category = Category("  Flask  ")
            question = Question(
                text="Как связать вопрос с категорией?",
                category=category,
            )
            Answer(question=question, is_agree=True)
            db.session.add(question)
            db.session.commit()

            saved_question = db.session.get(Question, question.id)
            assert saved_question is not None
            assert saved_question.category is not None
            assert saved_question.category.name == "Flask"
            assert len(saved_question.responses) == 1
            assert saved_question.responses[0].question is saved_question
            print("OK: Category, Question.category и Answer.question работают")
        finally:
            db.session.remove()


app = create_app()


if __name__ == "__main__":
    run_smoke_check()
