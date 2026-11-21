# Локальная контейнерная среда — этап 6

## Состав и изоляция

`compose.yml` запускает `db` (MySQL 8.4) и `web` (Django 5.2 / Python 3.14). Контейнеры используют отдельную внутреннюю сеть Compose и постоянный volume `mysql_data`. Порт MySQL на Mac не публикуется: служба Homebrew MySQL и её база не затрагиваются. HTTP доступен только на loopback Mac `127.0.0.1:18765` (значение `DJANGO_BIND_PORT`).

`Dockerfile` использует фиксированный Python minor и зависимости из `uv.lock`; в образ включены dev-зависимости для локального запуска полного набора тестов. Это окружение учебной локальной разработки: сервер Django `runserver --noreload` не используется как production WSGI, TLS, прокси и AWS-инфраструктуры здесь нет.

В рабочем каталоге нужен файл `.env` на основе `.env.example`, исключённый из Git. Три обязательных секрета — `DJANGO_SECRET_KEY`, `MYSQL_PASSWORD` и `MYSQL_ROOT_PASSWORD`; значения должны быть случайными и непустыми. Пример намеренно не содержит секретов. Локальный файл рекомендуется хранить с правами `0600`. Новый MySQL volume инициализируется данными только при первом запуске; изменение паролей в `.env` после инициализации само по себе не меняет пароли в существующей БД.

## Воспроизведение

Команды запуска из корня Django-репозитория:

```bash
docker compose config --quiet
docker compose up --build -d
docker compose ps
python3 infra/smoke_container.py
docker compose exec web python manage.py check
docker compose exec web python manage.py makemigrations --check --dry-run
docker compose --profile test run --build --rm tests
docker compose down
```

Автоматическое применение миграций выполняется перед запуском `web` после SQL-healthcheck `db`. Проверка `infra/smoke_container.py` выполняет только GET-запросы и проверяет коды 200/401/400. Контейнер `tests` — одноразовый профиль: для создания и удаления отдельной тестовой БД он подключается как MySQL root **только внутри изолированной Compose-сети**; само API работает от ограниченного `housing_app` в БД `housing_rental_compose`. Сохранённый volume после `docker compose down` остаётся на диске. Команды `down --volumes`, `system prune` и очистка чужих контейнеров не входят в процедуру.

Полезные диагностические команды:

```bash
docker compose logs --tail=80 web db
docker compose exec web python manage.py showmigrations
docker compose exec web python manage.py spectacular --validate --file /tmp/openapi.yaml
```

Локальные проверки реального MySQL могут продолжаться отдельно от контейнерной среды. Ни запуск AWS, ни публикация приложения в интернете этими командами не выполняются.
