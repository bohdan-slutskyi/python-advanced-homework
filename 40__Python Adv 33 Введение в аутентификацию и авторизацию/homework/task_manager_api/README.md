# Менеджер задач — JWT, permissions и глобальная пагинация

Проект продолжает API задач из предыдущих домашних работ. Добавлены
JWT-аутентификация SimpleJWT, разрешения Django REST Framework и глобальная
пагинация **по 5 объектов на страницу**. Сохранены CRUD задач, подзадач и
категорий, фильтрация, поиск, сортировка, статистика, мягкое удаление и
раздельное логирование HTTP и SQL.

## Подготовка и запуск

Требуется Python 3.12 или новее. Команды выполняются **из папки проекта**.

```bash
uv venv --python 3.12 .venv
uv pip install --python .venv/bin/python -r requirements.txt
cp .env.example .env
```

В файле `.env` замените `SECRET_KEY` на случайный локальный ключ. Его можно
получить без внешнего сервиса:

```bash
.venv/bin/python -c 'import secrets; print(secrets.token_urlsafe(48))'
```

`DEBUG=True` предназначено только для локальной демонстрации.
Затем подготовьте базу и 13 учебных задач:

```bash
.venv/bin/python manage.py migrate
.venv/bin/python manage.py loaddata fixtures/tasks.json
```

Создайте обычного пользователя через Django shell:

```bash
.venv/bin/python manage.py shell
```

```python
from django.contrib.auth import get_user_model
from getpass import getpass

User = get_user_model()
User.objects.create_user(username="student", password=getpass("Password: "))
```

Для проверки ограничения `IsAdminUser` создайте отдельно сотрудника
(`is_staff=True`) через `createsuperuser`:

```bash
.venv/bin/python manage.py createsuperuser
```

Запустите API:

```bash
.venv/bin/python manage.py runserver 127.0.0.1:8787 --noreload
```

Все аккаунты, пароли, JWT, локальная база, `.env`, `.venv` и логи исключены
из Git. Используйте HTTPS при доступе к API за пределами localhost.

## JWT: получение и обновление

Оба маршрута работают без уже выданного токена:

| Метод | URL | Запрос | Результат |
| --- | --- | --- | --- |
| POST | `/api/token/` | `username` и `password` | `access` и `refresh` |
| POST | `/api/token/refresh/` | `refresh` | новый `access` |

Пример JSON-тела запроса получения пары токенов:

```json
{"username": "student", "password": "<локальный пароль>"}
```

После получения `access` добавьте к защищённым запросам HTTP-заголовок
`Authorization: Bearer <access>`. Для обновления используйте отдельный
`refresh`-токен. Access действует 10 минут, refresh — 1 день. Эти значения
заданы через `SIMPLE_JWT` в `config/settings.py`. Не сохраняйте настоящие
токены в репозитории, скриншотах или публичных коллекциях.

## Матрица разрешений

Аутентификация глобально настроена через `JWTAuthentication`, а глобальный
permission по умолчанию — `IsAuthenticated`.

| API | Без токена | JWT пользователя | JWT сотрудника |
| --- | --- | --- | --- |
| GET/POST `/api/tasks/` | 401 | 200/201 | 200/201 |
| GET/PATCH/DELETE `/api/tasks/<id>/` | 401 | 200/200/204 | 200/200/204 |
| GET/POST `/api/subtasks/` | 401 | 200/201 | 200/201 |
| GET/PUT/PATCH/DELETE `/api/subtasks/<id>/` | 401 | Разрешено | Разрешено |
| GET `/api/categories/` и `/api/categories/<id>/` | 200 | 200 | 200 |
| POST/PATCH/DELETE для категорий | 401 | Разрешено | Разрешено |
| GET `/api/categories/count-tasks/` | 200 | 200 | 200 |
| GET `/api/tasks/statistics/` | 401 | 403 | 200 |

- Задачи и подзадачи защищены `IsAuthenticated` для всех операций.
- Категории используют `IsAuthenticatedOrReadOnly`: читать можно без токена,
  создавать, обновлять и удалять — только с JWT.
- Статистика задач использует `IsAdminUser` и требует `is_staff=True`.
- Неверный или истёкший токен возвращает 401. Авторизованный пользователь без
  административных прав получает 403 при запросе статистики.

Остальные маршруты, фильтры `status`, `deadline`, `task_title`,
`weekday`, `search`, `ordering` и мягкое удаление категорий сохранены.

## Глобальная пагинация

В `REST_FRAMEWORK` включена `PageNumberPagination` с `PAGE_SIZE=5`.
Она действует для списков задач, подзадач, категорий и `count-tasks`.
Ответ содержит `count`, `next`, `previous`, `results`.

```text
GET /api/tasks/          -> первые 5 задач
GET /api/tasks/?page=2   -> следующие 5 задач
GET /api/tasks/?page=3   -> последние 3 из 13 задач
```

Параметр `page_size` не даёт клиенту увеличить предел. Сортировка категорий
сделана устойчивой (`name`, `pk`). Для детальных маршрутов и статистики
глобальная пагинация не применяется: они возвращают один объект.

## Проверка

```bash
.venv/bin/python manage.py check
.venv/bin/python manage.py makemigrations --check --dry-run
.venv/bin/python manage.py test task_manager
```

Тесты проверяют получение/обновление JWT, неправильные токены и пароли,
401/403 для разных ролей, чтение и изменения задач и категорий, все четыре
списка по 5 записей, переходы по страницам, фильтры, CRUD, мягкое удаление,
статистику и раздельную запись HTTP/SQL-логов.

Для наглядного подтверждения в **Postman** выполните запросы:
`POST /api/token/`, `POST /api/token/refresh/`,
`GET /api/tasks/` без JWT и с Bearer JWT,
`GET /api/tasks/statistics/` от обычного пользователя и сотрудника,
`GET /api/tasks/?page=1`, `?page=2`, `?page=3`.
В итоговых скриншотах должны быть видны запрос, статус и ответ, но не
действующие токены или пароли.

Скриншоты сохранены в `screenshots/`:

- `01-unauthorized-401.png` — защищённый запрос без JWT.
- `02-member-page-1.png`, `03-member-page-2.png` и `04-member-page-3.png` —
  страницы списка задач; на последней странице виден завершающий набор записей.
- `05-member-forbidden-403.png` — обычному пользователю запрещён доступ к
  статистике задач.
- `06-staff-authorized-200.png` — сотрудник с `is_staff=True` получает доступ
  к статистике.
- `07-jwt-obtain-200.png` — сохранённый результат запроса `POST /api/token/`
  в Postman: HTTP 200 и пройденная проверка; тело с токенами и пароль скрыты.
  Обновление токена через `POST /api/token/refresh/` подтверждено отдельным
  автоматическим тестом `test_obtain_and_refresh_jwt`.

## Логи

- Консоль — события `django.server`.
- `logs/http_logs.log` — метод, путь и статус HTTP.
- `logs/db_logs.log` — запросы SQL при `DEBUG=True`.

Логи ротируются; URL-параметры, тело, cookies и заголовки в HTTP-журнал
не пишутся. SQL-журнал может содержать значения полей и предназначен только
для локальной отладки.
