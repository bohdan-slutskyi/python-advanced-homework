"""Фабрика Flask-приложения Community Pulse."""

from __future__ import annotations

from flask import Flask
from flask_migrate import Migrate

from app.models import db
from app.routers import answers_bp, categories_bp, questions_bp
from config import DevelopmentConfig

migrate = Migrate()


def create_app(database_url: str | None = None) -> Flask:
    """Создаёт приложение и подключает модели и маршрутизаторы."""

    app = Flask(__name__)
    app.config.from_object(DevelopmentConfig)

    if database_url is not None:
        app.config["SQLALCHEMY_DATABASE_URI"] = database_url

    db.init_app(app)
    migrate.init_app(app, db)
    app.register_blueprint(questions_bp)
    app.register_blueprint(answers_bp)
    app.register_blueprint(categories_bp)
    return app
