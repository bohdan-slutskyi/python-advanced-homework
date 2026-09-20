"""Маршрутизаторы API Community Pulse."""

from app.routers.answers import answers_bp
from app.routers.categories import categories_bp
from app.routers.questions import questions_bp

__all__ = ["answers_bp", "categories_bp", "questions_bp"]
