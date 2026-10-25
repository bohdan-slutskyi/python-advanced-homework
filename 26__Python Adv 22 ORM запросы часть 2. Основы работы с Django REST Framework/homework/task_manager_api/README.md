# Менеджер задач — API и статистика

Проект предоставляет API для создания задач, получения списка и отдельной
задачи, а также агрегированной статистики. Сериализатор использует модель
`Task`; новые API-маршруты реализованы function-based DRF views.

## Подготовка

Команды подготовки выполняются из каталога проекта:

```bash
uv venv --python 3.12 .venv
uv pip install --python .venv/bin/python -r requirements.txt
.venv/bin/python -c 'from pathlib import Path; import secrets; p=Path(".env"); p.exists() or p.write_text("SECRET_KEY=" + secrets.token_urlsafe(48) + "\nDEBUG=True\nALLOWED_HOSTS=127.0.0.1,localhost\n")'
.venv/bin/python manage.py migrate
```

Локальные настройки хранятся в `.env`, файл и SQLite база исключены из Git.
Миграции создают таблицы `Task`, `SubTask` и `Category`.

## Запуск

Локальный сервер запускается командой:

```bash
.venv/bin/python manage.py runserver 127.0.0.1:8774 --noreload
```

## Маршруты API

| Метод | Маршрут | Назначение | Успешный статус |
| --- | --- | --- | --- |
| `POST` | `/api/tasks/create/` | Создание задачи | `201 Created` |
| `GET` | `/api/tasks/` | Список задач | `200 OK` |
| `GET` | `/api/tasks/<id>/` | Одна задача по ID | `200 OK` |
| `GET` | `/api/tasks/statistics/` | Общая статистика | `200 OK` |

Тело запроса для создания задачи:

```json
{
  "title": "Prepare workshop materials",
  "description": "Prepare the workshop materials",
  "status": "new",
  "deadline": "2026-10-20T12:00:00Z"
}
```

Допустимые значения `status`: `new`, `in_progress`, `pending`, `blocked`,
`done`. Поля ответа задачи: `id`, `title`, `description`, `status`, `deadline`.
Невалидное тело запроса возвращает ошибки сериализатора с кодом `400`. Для
неизвестного ID возвращается `404 Not Found`.

Ответ статистики содержит число всех задач, количество записей для каждого
статуса (включая нулевые значения) и количество задач с `deadline` раньше
текущего времени UTC. Группировка выполняется ORM-агрегацией `Count`.

## Проверки

```bash
.venv/bin/python manage.py check
.venv/bin/python manage.py makemigrations --check --dry-run
```

Примеры ручных HTTP-запросов из каталога проекта:

```bash
curl -i -X POST http://127.0.0.1:8774/api/tasks/create/ \
  -H 'Content-Type: application/json' \
  --data '{"title":"Prepare workshop materials","description":"Prepare the workshop materials","status":"new","deadline":"2026-10-20T12:00:00Z"}'
curl -i http://127.0.0.1:8774/api/tasks/
curl -i http://127.0.0.1:8774/api/tasks/1/
curl -i http://127.0.0.1:8774/api/tasks/statistics/
```

Ручные запросы выполнены из интегрированного терминала VS Code. Снимки
показывают команду, вкладку Terminal, HTTP-статус и ответ API:

- [Создание задачи](screenshots/01_create_task.jpg)
- [Список задач](screenshots/02_task_list.jpg)
- [Получение задачи по ID](screenshots/03_task_detail.jpg)
- [Статистика задач](screenshots/04_task_statistics.jpg)
