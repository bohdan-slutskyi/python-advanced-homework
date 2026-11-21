# Аренда жилья — Django REST API

Итоговый проект программы **Python Developer**, IT Career Hub,
[LMS №271](https://lms.itcareerhub.de/course/view.php?id=271).
Backend аренды жилья с **Django 5.2 LTS, Django REST Framework, MySQL 8.4,
JWT**, пятью прикладными модулями и OpenAPI.

## Реализованные возможности

| Модуль | Реализация |
|---|---|
| **Accounts** | Custom User, регистрация, JWT access/refresh/logout, Django Groups Tenant/Landlord, права на уровне объекта |
| **Listings** | Создание, изменение и soft delete; активность; каталог, поиск, фильтры цены, комнат, типа жилья и географии; сортировка и пагинация |
| **Bookings** | PENDING/CONFIRMED/REJECTED/CANCELLED; права арендатора и владельца; отмена до дня заезда; транзакционная защита от подтверждения пересекающихся периодов |
| **Reviews** | Один отзыв (оценка 1–5) после завершённой подтверждённой брони; изменение собственного отзыва; агрегированный рейтинг |
| **Statistics** | Приватные истории поисков и просмотров, публичные агрегаты, порог приватности для популярных запросов |

Данные нормализованы до **3NF**. География хранится в `City` и `District`
с внешними ключами и уникальными парами (город, район). Публичный API
использует строковые значения городов/районов с проверкой справочника.
Цена `Booking.total_price` фиксируется при создании заявки и не изменяется
после изменения тарифа объекта. MySQL CHECK контролирует
`CANCELLED` → заполненный `cancelled_at`. Для периода проживания приняты
лимиты `MAX_STAY_NIGHTS=365` и `MAX_ADVANCE_BOOKING_DAYS=365`.

## Структура

- `config/` — настройки, маршруты, WSGI и ASGI;
- `apps/accounts/`, `apps/listings/`, `apps/bookings/`, `apps/reviews/`, `apps/statistics/` — модели, API, сервисы, миграции;
- `tests/` — модульные, API, интеграционные и конкурентные тесты MySQL;
- `postman/` — коллекция **41 запрос / 8 папок**, шаблоны окружений и генератор;
- `infra/` — сценарии HTTP, Docker/AWS EC2 Compose и конфигурация Nginx;
- `docs/` — [ER/3NF](docs/architecture/er-model.md),
  [архитектурные решения](docs/architecture/decisions.md),
  [матрица требований](docs/requirements-matrix.md),
  [целостность моделей](docs/model-integrity-2026-11-21.md);
- `presentation/` — [навигатор вопросов](presentation/defense-navigator.md)
  и [сценарий показа](presentation/demo-runbook.md).

API описан автоматически: `GET /api/schema/` и `GET /api/docs/`.

## Локальный запуск

Docker Compose использует MySQL 8.4 и Django в локальном контейнере;
на AWS применяется Gunicorn/Nginx. Конфигурация переменных задаётся через
исключённый из Git файл `.env` на основе [шаблона](.env.example).
В исходных файлах нет реальных паролей и токенов.

```bash
docker compose config --quiet
docker compose up -d --build
docker compose ps
python3 infra/smoke_container.py
docker compose --profile test run --rm tests
```

При запуске веб-контейнера выполняются миграции. Для демонстрационных данных
реализован `manage.py seed_demo` с Faker; отдельный HTTP-сценарий
`infra/demo_flow.py` проверяет регистрацию, роли, бронирования,
отзывы и статистику. Подробности: [Docker](docs/container-run.md) и
[сценарий демонстрации](presentation/demo-runbook.md).

## Фактические проверки

- **21.11.2026:** **91/91 Django unit/API/integration-тестов PASS на
  локальной MySQL**, включая конкурентные `TransactionTestCase`,
  проверку MySQL CHECK, строкового API, цены брони и воспроизводимость Postman.
- Миграции `listings.0004` и `bookings.0004` проверены на полной копии
  базы и применены к локальной Homebrew MySQL без потери 130 объявлений
  и 257 бронирований; `manage.py check`,
  `makemigrations --check --dry-run`, `migrate --check`, OpenAPI,
  Ruff — успешно.
- **18–19.11.2026:** Docker/MySQL — 84/84 теста, HTTP smoke 5/5;
  сквозной HTTP-сценарий — 60/60; прежние Postman проверки
  `Search & Filters` — 8/8.
- **19.11.2026:** AWS EC2 R25 был развёрнут и проверен
  (16 публичных HTTP assertions и 68 через защищённый SSH-forward);
  после проверки тот же EC2 остановлен с сохранённым EBS/MySQL.
  Обновление AWS схемой от 21.11 описано отдельно, не представляется
  как уже выполненное.

Постоянная база данных и тестовая БД разделены. В истории старых данных
сохранены исходные строки географии; неподтверждённые районы не
приписываются произвольным городам. Стоимости исторических бронирований
без известного исходного тарифа остаются NULL; новые заявки получают
зафиксированную полную цену. Результат полного нового Postman Runner и
контейнерной регрессии для схемы 21.11 пока не заявлен.
