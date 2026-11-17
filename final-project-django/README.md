# Python Developer — Final Project (Django)

Итоговый проект программы Python Developer, IT Career Hub, [LMS №271](https://lms.itcareerhub.de/course/view.php?id=271): REST backend аренды жилья на Django REST Framework и MySQL.

## Реализовано на 17.11.2026

- Django 5.2.19 LTS, Python 3.14.10, DRF 3.18.3, SimpleJWT 5.5.1, mysqlclient 2.3.1; зафиксированы `pyproject.toml`, `uv.lock` и `.python-version`.
- Пять приложений: `accounts`, `listings`, `bookings`, `reviews`, `statistics`. Custom User с email как логином создан в `accounts.0001_initial`; роли Tenant/Landlord представлены стандартными Django Groups через `accounts.0002_seed_groups`. Группы не взаимоисключающие.
- Начальные модели Listing, Booking, Review, SearchEvent, ViewEvent по ER/3NF-схеме. Listing использует soft delete; Booking сохраняет полуоткрытые даты и статусы; Review связан с одной Booking. На MySQL применены миграции, проверены CHECK, UNIQUE, FK и составные индексы. Реализованы модельные валидаторы дат и отзывов, нормализация текста поиска, проверка немецкого почтового индекса, DB-ограничения Choices и регистрозависимая колляция для кодов страны, типа жилья и статусов.
- Первый работающий API-сценарий: регистрация и вход, JWT refresh/logout с blacklist, защищённое создание/редактирование объявления владельцем, публичное чтение, включение и выключение видимости, мягкое удаление. Публичное получение неактивных и удалённых Listing запрещено; владелец видит собственное неактивное объявление.
- OpenAPI: `GET /api/schema/`; Swagger UI: `GET /api/docs/`.

## Реализованные HTTP-маршруты

| Метод | Путь | Назначение |
|---|---|---|
| POST | `/api/auth/register/` | Регистрация с автоматическим назначением Tenant |
| POST | `/api/auth/login/` | Получение access и refresh JWT |
| POST | `/api/auth/refresh/` | Обновление access JWT |
| POST | `/api/auth/logout/` | Отзыв принадлежащего пользователю refresh JWT |
| GET | `/api/auth/me/` | Проверка текущего пользователя и access JWT |
| GET | `/api/listings/`, `/api/listings/{id}/` | Публичный каталог и карточка |
| POST | `/api/listings/` | Создание объявления членом Landlord |
| PATCH | `/api/listings/{id}/` | Правка собственного объявления, в том числе `is_active` |
| DELETE | `/api/listings/{id}/` | Soft delete собственного объявления |

Landlord выдаётся только через доверенное управление Django Groups; публичного API повышения роли нет. JWT access остаётся действительным до своего срока истечения даже после blacklist refresh.

## Фактическая проверка

На локальном сервере MySQL **26.10.0**, InnoDB, `utf8mb4_0900_ai_ci` для таблиц/email и `utf8mb4_0900_bin` для полей Choices успешно применены миграции пяти приложений и Django/JWT; соединение работает в режиме `READ-COMMITTED`. Проверены ограничения дат, цены, числа комнат, рейтинга, уникальность email и Review.booking, исторические FK и индексы.

**21 автоматический тест и 15 параметризованных проверок прошли на MySQL**; дополнительно выполнены `manage.py check`, `makemigrations --check --dry-run`, `ruff check`, `ruff format --check` и валидация OpenAPI. Проведён реальный HTTP smoke-тест с кодами 201/200/404/204: регистрация → вход → объявление → скрытие → восстановление видимости → выход.

Воспроизводимость зависимостей обеспечена `uv.lock`. `.env.example` содержит только шаблон, `.env` и секреты в Git отсутствуют. Подключение к MySQL задаётся переменными окружения. Отдельная конфигурация пользователя БД с минимальными правами для развёртывания ещё не подготовлена.

## Следующие этапы и ограничения

API создания/подтверждения/отмены бронирований, защита от конкурирующих подтверждений, отзывы после завершённого проживания, поиск/фильтры/сортировка, аналитические события, Faker/Postman, Docker и развёртывание пока **не реализованы**. `Booking.clean()`, `Review.clean()` и `SearchEvent.clean()` проверяют модельные правила при явном `full_clean()`, но **обычный `save()` не вызывает `full_clean()` автоматически**: в API-сервисах будет предусмотрен явный вызов валидации. Для подтверждения бронирований запланированы транзакции с `SELECT FOR UPDATE` и конкурентный тест на MySQL.

Источники требований и решения D01–D14: [матрица](docs/requirements-matrix.md), [ER/3NF](docs/architecture/er-model.md), [диаграмма](docs/architecture/er-diagram.mmd), [решения](docs/architecture/decisions.md), [проверка моделей](docs/architecture/model-review.md).
