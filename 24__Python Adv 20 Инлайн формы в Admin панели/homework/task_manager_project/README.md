# Менеджер задач — инлайн-формы и действия Admin

Проект показывает связанные `Task` и `SubTask` в Django Admin. На странице
задачи подзадачи можно добавить в том же сохранении. В списке задач длинное
название сокращается до первых 10 символов и `...`, а поле выбора задачи в
форме подзадачи показывает полное название. Действие в списке подзадач
переводит отмеченные записи в статус `Done`.

## Подготовка

Команды подготовки выполняются из каталога проекта:

```bash
uv venv --python 3.12 .venv
uv pip install --python .venv/bin/python -r requirements.txt
.venv/bin/python -c 'from pathlib import Path; import secrets; p=Path(".env"); p.exists() or p.write_text("SECRET_KEY=" + secrets.token_urlsafe(48) + "\nDEBUG=True\nALLOWED_HOSTS=127.0.0.1,localhost\n")'
.venv/bin/python manage.py migrate
.venv/bin/python manage.py createsuperuser
```

Имя пользователя, email и пароль локального суперпользователя задаются при
выполнении команды `createsuperuser`.

## Запуск

```bash
.venv/bin/python manage.py runserver 127.0.0.1:8774
```

Адрес Django Admin: `http://127.0.0.1:8774/admin/`. Для работы используется
учётная запись суперпользователя, созданная при подготовке проекта. В разделе
Tasks форма задачи содержит inline-таблицу SubTask, позволяющую сохранить
задачу вместе с подзадачами. После сохранения записи отображаются в списках.
В списке Tasks названия длиннее 10 символов представлены первыми десятью
символами и многоточием. Поле Task в форме SubTask показывает полное название
связанной задачи. Действие **Mark selected subtasks as Done** в разделе
SubTasks присваивает статус `Done` выбранным записям.

## Проверка

```bash
.venv/bin/python manage.py check
.venv/bin/python manage.py makemigrations --check --dry-run
```

Инлайн использует модель `SubTask`, привязанную внешним ключом к `Task`.
Сокращение сделано отдельным столбцом Admin, поэтому исходное название модели
не меняется. Действие обновляет только выбранный QuerySet.

## Результат

Проверено на Django 6.1.1: `manage.py check` прошёл без ошибок,
`makemigrations --check --dry-run` не обнаружил изменений схемы. В админке
задача с двумя подзадачами сохранена одной формой; в списке название
сокращено, поле связи показывает полное название. Admin action изменил статус
только одной выбранной подзадачи: у неё отображается `Done`, вторая осталась
`New`.

- [Список задач с коротким названием](screenshots/01_task_list_short_title.jpg)
- [Статус выбранной подзадачи Done](screenshots/02_subtask_action_done.jpg)
- [Полное название связанной задачи](screenshots/03_full_task_reference.jpg)
