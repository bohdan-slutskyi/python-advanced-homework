# Task Manager API — JWT, владельцы, object permissions и Swagger

ДЗ 19 продолжает REST API из предыдущих домашних работ. Каждая новая задача и
подзадача автоматически получает владельца из `request.user`. Изменять или
удалять объект может только его владелец. Дополнительно доступны список задач
текущего пользователя и интерактивная документация Swagger/Redoc.

## Требования и подготовка

- Python 3.12+, `uv`;
- рабочая директория: папка этого проекта (`homework/task_manager_api`);
- локальная база SQLite (не публикуется);
- никаких реальных паролей и JWT в Git.

```bash
uv venv --python 3.12 .venv
uv pip install --python .venv/bin/python -r requirements.txt
cp .env.example .env
```

Замените в `.env` значение `SECRET_KEY` на локальный случайный секрет.
Сгенерировать его можно командой:

```bash
.venv/bin/python -c 'import secrets; print(secrets.token_urlsafe(48))'
```

Параметр `DEBUG=True` нужен только для локальных учебных проверок.

```bash
.venv/bin/python manage.py migrate
.venv/bin/python manage.py loaddata fixtures/tasks.json
.venv/bin/python manage.py createsuperuser
.venv/bin/python manage.py runserver 127.0.0.1:8787 --noreload
```

Чтобы создать обычного пользователя, используйте Django shell,
`get_user_model().objects.create_user(...)`; вводите пароль локально, не
сохраняйте его в файлах или скриншотах.

## JWT и текущий пользователь

| Метод | Маршрут | Действие |
| --- | --- | --- |
| POST | `/api/token/` | Получить `access` и `refresh` |
| POST | `/api/token/refresh/` | Получить новый `access` |
| GET | `/api/tasks/my/` | Задачи только текущего пользователя |

Запрос получения токенов содержит `username` и `password`.
Для защищённых маршрутов требуется заголовок `Authorization: Bearer <access>`.

Поле `owner` в моделях `Task` и `SubTask` — `ForeignKey` на пользователя.
Оно отображается в сериализаторах, но **недоступно для записи клиентом**.
Метод `perform_create` записывает `serializer.save(owner=self.request.user)`.
Поэтому нельзя назначить другого владельца передачей `owner` в JSON.

Старые записи из ДЗ 18 и учебной фикстуры не содержали владельца. Для
совместимой миграции поле `owner` допускает `NULL`, но **новые объекты через
API всегда получают владельца**. Старые записи без владельца видны при чтении,
не входят в `/api/tasks/my/` и не могут редактироваться через API, пока
администратор локальной базы явно не назначит им владельца. Например,
из Django shell можно выполнить `Task.objects.filter(owner__isnull=True).update(owner=user)`
и аналогично для `SubTask` после выбора нужного пользователя.

## Разрешения

`JWTAuthentication` остаётся способом аутентификации, а
`IsAuthenticated` — глобальным permission. Для Task и SubTask дополнительно
применяется собственный `IsOwnerOrReadOnly`:

| Операция | Без JWT | Владелец | Другой пользователь с JWT |
| --- | --- | --- | --- |
| GET списка/объекта | 401 | 200 | 200 |
| POST задачи | 401 | 201, owner из JWT | 201, owner из своего JWT |
| PATCH/PUT своей задачи | 401 | 200 | 403 |
| DELETE своей задачи | 401 | 204 | 403 |
| PATCH/PUT/DELETE чужой подзадачи | 401 | — | 403 |
| GET `/api/tasks/my/` | 401 | Только собственные | Только собственные |

При создании/изменении подзадачи дополнительно проверяется, что поле `task`
ссылается **на собственную задачу** пользователя. Попытка подменить
`owner` через тело запроса не меняет владельца.

Ранее реализованные разрешения категорий (`IsAuthenticatedOrReadOnly`) и
статистики (`IsAdminUser`) сохранены. Также сохранены фильтры, CRUD,
пагинация по 5, soft delete категорий и HTTP/SQL-логи.

## Swagger и Redoc

Установлен `drf-yasg`, включён `drf_yasg` в `INSTALLED_APPS`, добавлены
маршруты:

- <http://127.0.0.1:8787/swagger/> — Swagger UI;
- <http://127.0.0.1:8787/redoc/> — Redoc;
- <http://127.0.0.1:8787/swagger.json> — OpenAPI 2.0 JSON.

В Swagger доступна схема авторизации Bearer. Для реальных запросов
используется `Authorization: Bearer <access>`. Документация не требует
ввода личных данных или подключения аккаунта Postman.

## Проверка

```bash
.venv/bin/python manage.py check
.venv/bin/python manage.py makemigrations --check --dry-run
.venv/bin/python manage.py test task_manager --verbosity 2
.venv/bin/python verify_homework_19.py
```

Последняя команда проводит восемь проверок на локальной базе, создавая
временные учебные аккаунты и задачи в транзакции с откатом; они не остаются
после завершения. В консоль не выводятся пароли или JWT.

Тесты проверяют выдачу/refresh JWT, заполнение `owner` из
`request.user`, запрет подмены владельца, `/api/tasks/my/`, права доступа
401/403, создание и изменение подзадач, совместимость старых записей,
Swagger/Redoc и функциональность предыдущего ДЗ.

## Скриншоты

Четыре проверенных снимка из настоящих окон консоли и браузера:

- [01 — назначение владельца и запрет чужих изменений](screenshots/01-owner-permissions-console.png) — восемь реальных сценариев API; показаны коды 201, 200, 403 и 401.
- [02 — все автоматические тесты](screenshots/02-all-tests-console.png) — 16 тестов завершились успешно.
- [03 — Swagger UI](screenshots/03-swagger-task-manager.png) — документация маршрутов, включая список собственных задач.
- [04 — Redoc](screenshots/04-redoc-task-owner.png) — интерактивная документация и схемы запросов.

На кадрах нет паролей, действующих токенов и виртуального курсора.

## Безопасность

`.env`, `db.sqlite3`, `.venv`, `logs/` и кэши исключены из Git.
Это учебный проект; `DEBUG=True` и локальный сервер не предназначены для
боевого развёртывания.
