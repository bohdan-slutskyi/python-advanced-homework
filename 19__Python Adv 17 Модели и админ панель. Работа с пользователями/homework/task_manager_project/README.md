# Менеджер задач — модели и административная панель

Проект продолжает модели Task, SubTask и Category. У задач и подзадач
уникально название, у категорий — имя. `__str__` возвращает полный текст
названия. Задачи и подзадачи по умолчанию отсортированы от новых к старым.

| Модель | Таблица | verbose_name |
| --- | --- | --- |
| Task | task_manager_task | Task |
| SubTask | task_manager_subtask | SubTask |
| Category | task_manager_category | Category |

Уникальность обеспечена `unique=True` на уровне базы и форм админки.
Прежнее ограничение `unique_for_date` у Task заменено глобальной уникальностью.
Связи категорий и задач, а также задач и подзадач сохранены.

## Подготовка

Из этой папки:

```bash
uv venv --python 3.12 .venv
uv pip install --python .venv/bin/python -r requirements.txt
.venv/bin/python -c 'from pathlib import Path; import secrets; p=Path(".env"); p.exists() or p.write_text("SECRET_KEY=" + secrets.token_urlsafe(48) + "\nDEBUG=True\nALLOWED_HOSTS=127.0.0.1,localhost\n")'
.venv/bin/python manage.py migrate
.venv/bin/python manage.py createsuperuser
```

Пароль администратора вводится интерактивно. Для автоматической локальной
проверки допускается `createsuperuser --noinput --username local_admin
--email admin@example.test` с переменной `DJANGO_SUPERUSER_PASSWORD` в локальном
окружении. Пароли, `.env`, база и `.venv` не включаются в Git.

История миграций сохранена; новая миграция добавляет требования к метаданным
и уникальности. Перед применением к существующей базе нужно проверить
повторяющиеся названия задач и подзадач: миграция их автоматически не исправляет.

## Проверки

```bash
.venv/bin/python manage.py check
.venv/bin/python manage.py makemigrations --check --dry-run
.venv/bin/python manage.py test task_manager
```

После изменения моделей:

```bash
.venv/bin/python manage.py makemigrations task_manager
.venv/bin/python manage.py migrate
```

## Работа в админке

```bash
.venv/bin/python manage.py runserver 127.0.0.1:8773 --noreload
```

Адрес: `http://127.0.0.1:8773/admin/`. Остановка — `Ctrl+C`.
Часовой пояс проекта — UTC; даты в формах вводятся в UTC.

1. Войдите под локальным администратором.
2. Создайте категории, например «Разработка» и «Документация».
3. Создайте задачи с описанием, статусом, сроком и категориями.
4. Создайте подзадачи, выбирая соответствующую задачу.
5. Проверьте списки, поиск по тексту и фильтр статуса.

`TaskAdmin` показывает название, статус, срок и дату создания; доступны поиск,
фильтры и выбор нескольких категорий. `SubTaskAdmin` дополнительно показывает
родительскую задачу. В `CategoryAdmin` есть поиск и сортировка по имени.
Дата создания доступна только для чтения.

Инлайн-формы, укороченные названия и действия над статусами относятся
к отдельному продолжению и здесь не добавляются.

## Демонстрационные записи

Через формы админки созданы две категории, две задачи и две подзадачи.
Их состояние сохранено в `fixtures/demo.json`, без учётных записей.
Чтобы восстановить записи на новой базе после миграций:

```bash
.venv/bin/python manage.py loaddata fixtures/demo.json
```

Этот импорт предназначен для новой учебной базы: fixture использует фиксированные
ID и может обновить совпадающие записи. Для существующих личных данных его
не применяют без проверки.

Экспорт демонстрационных объектов:

```bash
.venv/bin/python manage.py dumpdata task_manager --indent 2 --output fixtures/demo.json
```

В локальной базе создан администратор `local_admin`. Его автоматически
сгенерированный пароль хранится только в локальном `.env` как
`DJANGO_SUPERUSER_PASSWORD`; в fixture и репозиторий он не входит.
При новом запуске на другой базе создайте своего администратора.

## Проверка результата

На Python 3.12.13 / Django 6.1.1 миграции применены, `check` прошёл без ошибок,
`makemigrations --check --dry-run` не обнаружил изменений.
Все 11 автотестов прошли. Они проверяют строковые представления, метаданные и реальные таблицы,
уникальность в базе, сортировку, связи, формы, отклонение дубликатов,
поиск и фильтры, а также восстановление демонстрационных записей.

Через браузер подтверждены создание и отображение объектов.
Скриншоты списков:

- [Категории](screenshots/categories.png)
- [Задачи](screenshots/tasks.png)
- [Подзадачи](screenshots/subtasks.png)

Сервер после проверки остановлен.
Код проекта: [Менеджер задач на GitHub](https://github.com/bohdan-slutskyi/python-advanced-homework/tree/main/19__Python%20Adv%2017%20%D0%9C%D0%BE%D0%B4%D0%B5%D0%BB%D0%B8%20%D0%B8%20%D0%B0%D0%B4%D0%BC%D0%B8%D0%BD%20%D0%BF%D0%B0%D0%BD%D0%B5%D0%BB%D1%8C.%20%D0%A0%D0%B0%D0%B1%D0%BE%D1%82%D0%B0%20%D1%81%20%D0%BF%D0%BE%D0%BB%D1%8C%D0%B7%D0%BE%D0%B2%D0%B0%D1%82%D0%B5%D0%BB%D1%8F%D0%BC%D0%B8/homework/task_manager_project).
