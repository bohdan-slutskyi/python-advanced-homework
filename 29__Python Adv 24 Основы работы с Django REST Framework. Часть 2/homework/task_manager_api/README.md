# Менеджер задач — сериализаторы и API подзадач

Проект включает API задач и категорий, вложенное отображение связанных
подзадач, валидацию срока выполнения и CRUD API подзадач на `APIView`.

## Подготовка

Команды выполняются из каталога проекта:

```bash
uv venv --python 3.12 .venv
uv pip install --python .venv/bin/python -r requirements.txt
cp .env.example .env
```

Перед первым запуском в `.env` задаётся локальное значение `SECRET_KEY`.
Файл `.env`, виртуальное окружение и база данных не добавляются в Git.

```bash
.venv/bin/python manage.py migrate
```

## Запуск и маршруты

```bash
.venv/bin/python manage.py runserver 127.0.0.1:8774 --noreload
```

| Метод | Маршрут | Назначение |
| --- | --- | --- |
| `POST` | `/api/tasks/create/` | Создание задачи; срок должен быть в будущем |
| `GET` | `/api/tasks/` | Список задач |
| `GET` | `/api/tasks/<id>/` | Детали задачи со всеми связанными подзадачами |
| `GET` | `/api/tasks/statistics/` | Статистика задач |
| `GET`, `POST` | `/api/subtasks/` | Список и создание подзадач |
| `GET`, `PUT`, `PATCH`, `DELETE` | `/api/subtasks/<id>/` | Получение, полное/частичное обновление и удаление |

У `SubTaskCreateSerializer.created_at` только режим чтения. Проверки
дубликатов категорий выполняются отдельно для создания и обновления.
Невалидные данные возвращают `400`, отсутствующая подзадача — `404`,
успешное создание — `201`, удаление — `204` без тела ответа.

## Проверки

```bash
.venv/bin/python manage.py check
.venv/bin/python manage.py makemigrations --check --dry-run
.venv/bin/python manage.py test task_manager
```
