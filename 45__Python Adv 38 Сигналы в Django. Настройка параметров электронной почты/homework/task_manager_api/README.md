# ДЗ 21 — уведомления владельца при изменении статуса основной задачи

Полноценный Django REST API задач, продолжающий ДЗ 20. Новая функциональность: Django-сигналы для email-уведомлений владельца при фактическом изменении статуса основной задачи, включая закрытие. Письма выводятся в консоль; SMTP не требуется. Сохранены регистрация, вход, автоматическое использование JWT из HttpOnly cookies, обновление access-токена, выход и отзыв токенов на сервере. Сохранены CRUD задач/подзадач/категорий, права владельцев, список собственных задач, статистика, фильтры, пагинация по 5, логи, Swagger и Redoc.

## Запуск

Требуется Python 3.12+ и `uv`. Все команды выполняются **из папки проекта**.

```bash
uv venv --python 3.12 .venv
uv pip install --python .venv/bin/python -r requirements.txt
cp .env.example .env
```

Локальная конфигурация `.env` использует отдельный случайный `SECRET_KEY`. Команда генерации ключа:

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
- Команда `.venv/bin/python manage.py flushexpiredtokens` очищает просроченные записи SimpleJWT. Отозванные access-токены хранятся в `RevokedAccessToken` с датой истечения `expires_at`.

## Уведомления о статусах — ДЗ 21

- Отслеживается только основная модель `Task`, не `SubTask`. Обработчики `pre_save` и `post_save` подключены в `TaskManagerConfig.ready()`.
- При сохранении существующей задачи с **другим** статусом владельцу (`Task.owner.email`) отправляется одно письмо, содержащее название задачи, прежний и новый статусы. При `done` дополнительно указывается закрытие.
- Новая задача, повторное сохранение `done`, изменения только описания/названия и вызов `save(update_fields=...)` без `status` не вызывают уведомление. При отсутствии владельца или его email письмо не отправляется.
- Отправка запланирована через `transaction.on_commit()` — после успешного завершения транзакции; при откате письма нет.
- `EMAIL_BACKEND` установлен в `django.core.mail.backends.console.EmailBackend`; реальные письма никому не отправляются. `DEFAULT_FROM_EMAIL` использует тестовый адрес `no-reply@example.test`.
- Сигналы Django вызываются для `model.save()` и обычных API PATCH/PUT через сериализатор. `QuerySet.update()` и `bulk_update()` обходят `save()`, поэтому уведомления при таких изменениях не формируются.

Фактическая проверка: для тестового владельца с адресом `owner@example.test` выполнены переходы задачи `new → in_progress → done`. Консольный backend вывел два письма с заголовками `Subject`, `To` и предыдущим/новым статусами. Повторное сохранение `done` не вызвало третьего уведомления.

## Автоматические проверки

```bash
.venv/bin/python manage.py check
.venv/bin/python manage.py makemigrations --check --dry-run
.venv/bin/python manage.py test task_manager --verbosity 2
ALLOWED_HOSTS=127.0.0.1,localhost,testserver .venv/bin/python verify_homework_20.py
```

**Прежние 33 автоматических теста** проверяют новую регистрацию, хеширование и сложность пароля, уникальность username/email, вход, CSRF, HttpOnly-cookie, refresh rotation, автоматическое обновление access, logout, blacklist и защиту старых токенов. Также повторно проверяются 16 сценариев ДЗ 18–19: CRUD, фильтры, permissions, owner, Swagger/Redoc, пагинация и логи.

`test_signals.py` добавляет 12 проверок: переходы статусов, закрытие, повторные сохранения, отсутствие email, права доступа, откат транзакции, реальный вывод консольного backend.

`verify_homework_20.py` проводит сквозной сценарий от регистрации до окончательного logout, проверяет статусы ответов и удаляет созданные записи откатом транзакции. Пароли, JWT и значения ключей в консоль не выводятся.

## Скриншоты результатов ДЗ 21

- [45 автоматических тестов — OK](screenshots/03-hw21-45-tests-passed.png).
- [Уведомления при смене статуса задачи — два письма в консоли](screenshots/04-hw21-console-email-notifications.png).

## Состав решения

В репозитории сохранены исходный код, миграции, учебные фикстуры, README и скриншоты результатов ДЗ 21. Локальные `.env`, `.venv`, SQLite и логи в состав решения не входят.
