# Менеджер задач — категории и мягкое удаление

Категории доступны через `CategoryViewSet` на основе `ModelViewSet`.
Маршруты CRUD и дополнительных действий зарегистрированы через `DefaultRouter`.
Категории назначаются задачам через поле `categories`, содержащее список ID.

## Подготовка и запуск

Команды выполняются из папки проекта. Требуется Python 3.12 или новее.

```bash
uv venv --python 3.12 .venv
uv pip install --python .venv/bin/python -r requirements.txt
cp .env.example .env
```

В `.env` задаётся локальное значение `SECRET_KEY`. Далее выполняются миграции
и запуск сервера:

```bash
.venv/bin/python manage.py migrate
.venv/bin/python manage.py runserver 127.0.0.1:8785 --noreload
```

Адрес категорий: http://127.0.0.1:8785/api/categories/.
Окружение, локальная конфигурация и база данных исключены из Git.

## Маршруты категорий

| Метод | Маршрут | Назначение |
| --- | --- | --- |
| GET, POST | `/api/categories/` | Список активных категорий и создание |
| GET, PUT, PATCH, DELETE | `/api/categories/<id>/` | Получение, полное и частичное обновление, мягкое удаление |
| GET | `/api/categories/count-tasks/` | Количество связанных задач для каждой активной категории |
| GET | `/api/categories/<id>/count-tasks/` | Количество задач одной активной категории |

Пример создания категории:

```json
{"name": "Planning"}
```

В ответах категории присутствуют `id`, `name`, `is_deleted`, `deleted_at`.
Поля `id`, `is_deleted` и `deleted_at` доступны только для чтения.
Пустое или повторяющееся название возвращает HTTP 400. Уникальность названия
сохраняется и для удалённых категорий: повторное создание такого названия
также возвращает HTTP 400.

## Подсчёт связанных задач

Действие `count_tasks` оформлено через `@action(detail=False)`.
Оно возвращает массив объектов с полями `id`, `name`, `tasks_count`.
Количество вычисляется ORM-агрегацией `Count`, без отдельного запроса для
каждой категории. Пустые категории включаются с количеством 0,
удалённые категории не включаются.

Для одной категории предусмотрено отдельное действие с `detail=True`.

Пример тела POST-запроса на `/api/tasks/` после создания категории с ID 1:

```json
{
  "title": "Prepare release",
  "description": "Prepare project release",
  "status": "new",
  "deadline": "2026-12-20T12:00:00Z",
  "categories": [1]
}
```

Срок задачи должен находиться в будущем; дата в примере заменяется при
повторении после этого срока. ID в `categories` должны соответствовать
существующим активным категориям. При обновлении задачи поле `categories`
заменяет набор связей, пустой массив снимает их.

## Мягкое удаление

DELETE категории устанавливает `is_deleted=True` и текущее время в
`deleted_at`; сама строка не удаляется из базы. Ответ — HTTP 204.
Повторное чтение или удаление через API возвращает HTTP 404.

`Category.objects` использует менеджер с фильтром `is_deleted=False`.
Через `Category.all_objects` доступны также удалённые записи.
Мягкое удаление предусмотрено и для экземпляра, и для `QuerySet.delete()`.
Повторный вызов `delete()` того же экземпляра не меняет исходное время удаления.

Связанные задачи и строки промежуточной таблицы сохраняются. Удалённая
категория скрывается из списка категорий задачи и не может назначаться
новым задачам через API. Восстановление и физическое удаление через API
не предусмотрены.

Проверка сохранённой записи через Django shell:

```bash
.venv/bin/python manage.py shell
```

```python
from task_manager.models import Category
list(Category.all_objects.filter(is_deleted=True).values("id", "name", "is_deleted", "deleted_at"))
```

## API задач и подзадач

Сохранены Generic Views задач и подзадач, фильтры `status`, `deadline`,
поиск `search` по названию и описанию, сортировка `ordering=created_at`
и `ordering=-created_at`. Детали задачи включают `categories` и `subtasks`.

Также сохранены `weekday` для задач, `task_title` для подзадач и пагинация
подзадач по 5 объектов. Статистика доступна по `/api/tasks/statistics/`.

## Проверки

```bash
.venv/bin/python manage.py check
.venv/bin/python manage.py makemigrations --check --dry-run
.venv/bin/python manage.py test task_manager
```

Все 30 тестов прошли: CRUD, сериализаторы, фильтры и пагинация задач,
CRUD категорий, подсчёт задач, защита служебных полей, мягкое удаление
экземпляра и QuerySet, сохранность связей, уникальность названий,
запрет назначения удалённых категорий и HTML-интерфейс API.

## Скриншоты API

| Проверка | Ответ | Скриншот |
| --- | --- | --- |
| Создание категории | POST, 201 | [Создание](screenshots/01_category_create.jpg) |
| Получение категории | GET, 200 | [Чтение](screenshots/02_category_read.jpg) |
| Обновление категории | PUT, 200 | [Обновление](screenshots/03_category_update.jpg) |
| Создание задачи с категорией | POST, 201 | [Связь с задачей](screenshots/04_task_category.jpg) |
| Количество задач по категориям | GET, 200 | [Подсчёт](screenshots/05_count_tasks.jpg) |
| Мягкое удаление категории | DELETE, 204 | [Удаление](screenshots/06_category_delete.jpg) |
| Удалённая категория скрыта | GET, 404 | [Повторное чтение](screenshots/07_category_hidden.jpg) |
| Список активных категорий | GET, 200 | [Список](screenshots/08_active_categories.jpg) |
| Задача сохранена после удаления категории | GET, 200 | [Сохранность задачи](screenshots/09_task_preserved.jpg) |
