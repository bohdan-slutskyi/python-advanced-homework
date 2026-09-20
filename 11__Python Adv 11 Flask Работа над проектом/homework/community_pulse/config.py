"""Конфигурация учебного приложения Community Pulse."""

from __future__ import annotations

import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
INSTANCE_DIR = BASE_DIR / "instance"
DEFAULT_DATABASE_URL = f"sqlite:///{INSTANCE_DIR / 'community_pulse.sqlite3'}"


class DevelopmentConfig:
    """Конфигурация для локального запуска проекта."""

    SECRET_KEY = os.environ.get("SECRET_KEY", "community-pulse-lesson-11")
    SQLALCHEMY_DATABASE_URI = os.environ.get(
        "DATABASE_URL",
        DEFAULT_DATABASE_URL,
    )
    SQLALCHEMY_TRACK_MODIFICATIONS = False
