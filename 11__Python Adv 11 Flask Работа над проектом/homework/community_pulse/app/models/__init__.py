"""Модели и общий объект Flask-SQLAlchemy."""

from flask_sqlalchemy import SQLAlchemy

db = SQLAlchemy()

from .answers import Answer, Statistic
from .category import Category
from .questions import Question

__all__ = ["Answer", "Category", "Question", "Statistic", "db"]
