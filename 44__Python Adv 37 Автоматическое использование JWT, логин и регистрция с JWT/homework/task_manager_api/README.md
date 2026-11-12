# ДЗ 20 — регистрация, вход и выход с JWT в HttpOnly cookies

Полноценный Django REST API, продолжающий предыдущие домашние работы. Добавлены регистрация, вход, автоматическое использование JWT из cookies, обновление access-токена, выход и отзыв токенов на сервере. Сохранены CRUD задач/подзадач/категорий, права владельцев, список собственных задач, статистика, фильтры, пагинация по 5, логи, Swagger и Redoc.

## Запуск

Требуется Python 3.12+ и `uv`. Все команды выполняются **из папки проекта**.

```bash
uv venv --python 3.12 .venv
uv pip install --python .venv/bin/python -r requirements.txt
cp .env.example .env
```

В `.env` значение `SECRET_KEY` необходимо заменить на случайное локальное значение. Для генерации ключа используется команда:

```bash
.venv/bin/python -c 'import secrets; print(secrets.token_urlsafe(48))'
```

Для локальной демонстрации используется `DEBUG=True`. Далее:

```bash
.venv/bin/python manage.py migrate
.venv/bin/python manage.py loaddata fixtures/tasks.json
.venv/bin/python manage.py runserver 127.0.0.1:8792 --noreload
```

В отличие от прежних ДЗ, в проекте подключён `rest_framework_simplejwt.token_blacklist` и миграция `RevokedAccessToken`.

## Маршруты аутентификации

| Метод | Маршрут | Результат |
| --- | --- | --- |
| GET | `/api/auth/csrf/` | Выдаёт CSRF cookie для безопасных POST |
| POST | `/api/register/` | Валидирует и регистрирует пользователя, сохраняет JWT в cookies; HTTP 201 |
| POST | `/api/login/` | Проверяет логин/пароль, сохраняет JWT в cookies; HTTP 200 |
| POST | `/api/auth/refresh/` | Обновляет access через refresh cookie и ротирует refresh; HTTP 200 |
| POST | `/api/logout/` | Заносит access в blacklist, отзывает refresh, удаляет cookies; HTTP 204 |
| GET | `/api/tasks/my/` | Защищённый список собственных задач с JWT |

Для совместимости с ДЗ 18–19 маршруты `POST /api/token/` и `POST /api/token/refresh/` по-прежнему работают с JSON-токенами и заголовком `Authorization: Bearer <access>`.

## Проверка регистрации

Пример JSON для POST `/api/register/`:

```json
{
  "username": "newstudent",
  "email": "newstudent@example.test",
  "password": "<сильный локальный пароль>"
}
```

Регистрация проверяет обязательность полей, формат логина и email, уникальность логина и email без учёта регистра, минимальную длину пароля, сходство с данными пользователя, распространённые и числовые пароли. Дополнительно требуются прописная и строчная буквы, цифра и спецсимвол. Пароль сохраняется только через Django `create_user()` с хешированием. Поле `password` никогда не возвращается клиенту.

Пример ответа:

```json
{"user": {"username": "newstudent", "email": "newstudent@example.test"}}
```

В ответе нет JWT-токенов в JSON. Они устанавливаются двумя **HttpOnly cookies**: `access_token` и `refresh_token` с `SameSite=Lax`, `Path=/api/`, ограниченным сроком жизни и `Secure=True` при `DEBUG=False`. При запуске на localhost по HTTP для демонстрации `Secure=False`; для внешних подключений обязателен HTTPS.

## CSRF и использование cookies

При работе через браузер или Postman сначала выполняется запрос `GET /api/auth/csrf/`, после чего сохраняется cookie `csrftoken`. Для каждого POST/PATCH/PUT/DELETE с cookie-аутентификацией требуется заголовок:

```text
X-CSRFToken: <значение cookie csrftoken>
```

При cookie-входе токен доступа извлекается сервером автоматически. Ручной заголовок Bearer не нужен. При истечении access на **безопасном GET** система может автоматически обновить его с помощью действительного refresh и установить новые cookies. Для небезопасных запросов (POST/PATCH/DELETE) автоматической ротации нет: необходимо отдельно выполнить `POST /api/auth/refresh/` с CSRF-заголовком и затем повторить исходный запрос.

Авторизация через явный заголовок Bearer остаётся доступной API-клиентам без cookies. Cookie-запросы проверяются через CSRF, чтобы браузер не мог незаметно отправлять изменения от имени пользователя.

## Обновление и выход

- Access действует 10 минут, refresh — 1 день.
- `ROTATE_REFRESH_TOKENS=True` и `BLACKLIST_AFTER_ROTATION=True`. Использованный refresh при обновлении заносится в SimpleJWT blacklist и не может быть предъявлен снова.
- При `POST /api/logout/` текущий refresh заносится в SimpleJWT blacklist, а текущий access — в таблицу `RevokedAccessToken` по `jti` и `exp` (сам JWT в БД не хранится). Обе cookies удаляются с тем же `Path`.
- Повторно использовать access в Bearer после logout нельзя: сервер проверяет blacklist и возвращает HTTP 401.
- При недействительном refresh ручное обновление возвращает 401 и очищает cookies.
- Просроченные записи SimpleJWT можно очищать командой `.venv/bin/python manage.py flushexpiredtokens`. Записи отозванных access-токенов следует периодически очищать после срока `expires_at` при эксплуатации вне учебной среды.

## Автоматические проверки

```bash
.venv/bin/python manage.py check
.venv/bin/python manage.py makemigrations --check --dry-run
.venv/bin/python manage.py test task_manager --verbosity 2
.venv/bin/python verify_homework_20.py
```

**33 автоматических теста** проверяют новую регистрацию, хеширование и сложность пароля, уникальность username/email, вход, CSRF, HttpOnly-cookie, refresh rotation, автоматическое обновление access, logout, blacklist и защиту старых токенов. Также повторно проверяются 16 сценариев ДЗ 18–19: CRUD, фильтры, permissions, owner, Swagger/Redoc, пагинация и логи.

`verify_homework_20.py` проводит сквозной сценарий от регистрации до окончательного logout, проверяет статусы ответов и удаляет созданные записи откатом транзакции. Пароли, JWT и значения ключей в консоль не выводятся.

## Приложения

Реальные скриншоты из терминала VS Code:

- [01 — регистрация, вход, refresh и выход](screenshots/01-registration-login-logout.png): коды 200/201/204/401, HttpOnly cookies и отзыв JWT.
- [02 — все 33 автоматических теста](screenshots/02-33-tests-passed.png): полный итог Ran 33 tests / OK.

На снимках нет действующих JWT, паролей, содержимого секретных файлов или виртуального курсора.

## Безопасность и ограничения

Это учебный проект, **не готовый к размещению в интернете**. Перед реальным развёртыванием необходимы TLS, безопасные cookies, ограничения частоты запросов, защита аккаунтов от перебора и контроль жизненного цикла токенов. CSRF cookie и `X-CSRFToken` защищают от обычных межсайтовых запросов, но не заменяют HTTPS и защиту от XSS.

`.env`, `.venv`, SQLite, cookie-хранилища, логи, токены и пароли исключены из Git. Репозиторий содержит только код, миграции, учебные JSON-фикстуры, README и доказательства работы.
