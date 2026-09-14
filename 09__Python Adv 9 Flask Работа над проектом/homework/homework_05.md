# Python Advanced: Домашнее задание 5

- **Источник LMS:** <https://lms.itcareerhub.de/mod/assign/view.php?id=15673>
- **Статус:** точное условие LMS сохранено; решение добавлено ниже отдельным разделом

Цели задания:

Расширить функциональность существующего API для поддержки категорий вопросов.

Задачи:

Создание модели Category:

Создайте новую модель Category с использованием SQLAlchemy в модуле models.

Модель должна содержать следующие поля:

id: первичный ключ, целое число, авто-инкремент.

name: строка, название категории, не должно быть пустым.

Модель Question должна быть обновлена, чтобы включить ссылку на Category через внешний ключ.

Миграция базы данных:

Создайте новую миграцию для добавления таблицы категорий и обновления таблицы вопросов с использованием Flask-Migrate.

## Решение

### Граница решения

Решение использует только сущности, разрешённые накопительной границей до
урока 09: `db.Model`, `db.Column`, `db.ForeignKey`, `db.relationship`,
Flask-SQLAlchemy, фабрику приложения, `Blueprint` и Flask-Migrate.

### 1. Модель `Category`

Создаём отдельный модуль `app/models/category.py`:

```python
from app.models import db


class Category(db.Model):
    __tablename__ = 'categories'

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    name = db.Column(db.String(100), nullable=False)
    questions = db.relationship('Question', back_populates='category')

    def __init__(self, name: str) -> None:
        normalized_name = name.strip()
        if not normalized_name:
            raise ValueError('Название категории не может быть пустым')
        self.name = normalized_name
```

`nullable=False` запрещает значение `NULL` в базе данных, а проверка в
конструкторе дополнительно запрещает пустую или состоящую только из пробелов
строку при создании объекта.

### 2. Связь с существующей моделью `Question`

В существующий `app/models/questions.py` добавляем в класс `Question` два
поля, не удаляя уже имеющиеся поля и связь с `Response`:

```python
category_id = db.Column(
    db.Integer,
    db.ForeignKey('categories.id'),
    nullable=True,
)
category = db.relationship('Category', back_populates='questions')
```

На первом этапе `category_id` оставлен nullable. Это позволяет безопасно
изменить уже существующую таблицу `questions`, если в ней есть старые записи,
для которых категория ещё не назначена. После заполнения категорий можно
отдельной миграцией ужесточить ограничение до `nullable=False`, если это будет
отдельным требованием проекта.

### 3. Регистрация моделей и расширения базы

В `app/models/__init__.py` оставляем единственный объект расширения базы и
импортируем модели после его создания:

```python
from flask_sqlalchemy import SQLAlchemy


db = SQLAlchemy()

# Импорты нужны Flask-Migrate для обнаружения всех таблиц в metadata.
from app.models.category import Category
from app.models.questions import Question
```

Если в проекте уже есть модели `Response` или `Statistic`, их существующие
импорты в этом файле сохраняются.

В `app/__init__.py` подключаем `db`, Flask-Migrate и существующий blueprint:

```python
from flask import Flask
from flask_migrate import Migrate

from app.models import db
from app.routers.questions import questions_bp


def create_app(config_object=None):
    app = Flask(__name__)

    if config_object is None:
        mode = os.environ.get('APP_ENV', 'development')
        config_object = CONFIG_MAP[mode]

    app.config.from_object(config_object)

    db.init_app(app)

    migrate = Migrate()
    migrate.init_app(app, db)

    app.register_blueprint(questions_bp)
    return app
```

В начале этого файла сохраняется существующий импорт `os`. Конфигурация
`SQLALCHEMY_DATABASE_URI` уже находится в `config.py` и для этого задания не
дублируется.

### 4. Создание и применение миграции

Команды выполняются из корня приложения. `db init` запускается
только один раз, если каталога `migrations/` ещё нет:

```bash
flask --app run.py db init
flask --app run.py db migrate \
  -m 'add categories and question category'
flask --app run.py db upgrade
```

Команды запускаются в локальном окружении проекта, управляемом через `uv`; для
них не требуется глобальная установка пакетов.

После `db migrate` проверяем сгенерированный файл в
`migrations/versions/`. В нём должны быть операции для:

- создания таблицы `categories` с первичным ключом `id` и обязательным `name`;
- добавления `category_id` в `questions`;
- создания внешнего ключа `questions.category_id` → `categories.id`.

Для проверки отката последней миграции используется команда из материала
урока:

```bash
flask --app run.py db downgrade
```

После проверки миграцию снова применяют командой `db upgrade`. В результате
получается таблица категорий и связь вопросов с категориями без изменения
системного Python и без глобальных установок.
