"""Точка входа для локального запуска Community Pulse."""

# Команда запуска из каталога проекта: uv run --locked python run.py

from app import create_app
from app.models import db

app = create_app()


if __name__ == "__main__":
    # Для простого запуска учебного проекта база создаётся автоматически.
    # Контролируемое изменение схемы выполняется через Flask-Migrate.
    with app.app_context():
        db.create_all()
    app.run(debug=True)
