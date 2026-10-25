# Python Advanced: Домашнее задание 12

- **Источник LMS:** <https://lms.itcareerhub.de/mod/assign/view.php?id=15724>

Домашнее задание: Проект "Менеджер задач" — Создание API для управления задачами

Цель: Освоить работу с Django REST Framework для создания, получения и агрегирования данных, используя модели задач.

Задание 1: Эндпоинт для создания задачи

Создайте эндпоинт для создания новой задачи. Задача должна быть создана с полями title, description, status, и deadline.

Шаги для выполнения:

Определите сериализатор для модели Task.

Создайте представление для создания задачи.

Создайте маршрут для обращения к представлению.

Задание 2: Эндпоинты для получения списка задач и конкретной задачи по её ID

Создайте два новых эндпоинта для:

Получения списка задач

Получения конкретной задачи по её уникальному ID

Шаги для выполнения:

Создайте представления для получения списка задач и конкретной задачи.

Создайте маршруты для обращения к представлениям.

Задание 3: Агрегирующий эндпоинт для статистики задач

Создайте эндпоинт для получения статистики задач, таких как общее количество задач, количество задач по каждому статусу и количество просроченных задач.

Шаги для выполнения:

Определите представление для агрегирования данных о задачах.

Создайте маршрут для обращения к представлению.

Оформите ваш ответ следующим образом:

Код эндпоинтов: Вставьте весь код представлений и маршрутов.

Скриншоты ручного тестирования: Приложите скриншоты консоли или Postman, подтверждающие успешное выполнение запросов для каждого эндпоинта.

## Решение

Реализация находится в отдельном запускаемом проекте `task_manager_api` в этой папке. Сериализатор ограничивает API полями задачи, указанными в условии. Представления разделяют создание, получение списка, получение одной записи и статистику. Маршруты подключены под `/api/`.

### Сериализатор (`task_manager/serializers.py`)

```python
from rest_framework import serializers

from .models import Task


class TaskSerializer(serializers.ModelSerializer):
    class Meta:
        model = Task
        fields = ("id", "title", "description", "status", "deadline")
        read_only_fields = ("id",)
```

`ModelSerializer` строит поля и проверку данных на основе модели `Task`. Идентификатор выдаётся базой данных и доступен только для чтения.

### Представления (`task_manager/views.py`)

```python
from django.db.models import Count
from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework import status
from rest_framework.decorators import api_view
from rest_framework.response import Response

from .models import STATUS_CHOICES, Task
from .serializers import TaskSerializer


@api_view(["POST"])
def task_create(request):
    serializer = TaskSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)
    serializer.save()
    return Response(serializer.data, status=status.HTTP_201_CREATED)


@api_view(["GET"])
def task_list(request):
    serializer = TaskSerializer(Task.objects.all(), many=True)
    return Response(serializer.data)


@api_view(["GET"])
def task_detail(request, pk: int):
    task = get_object_or_404(Task, pk=pk)
    serializer = TaskSerializer(task)
    return Response(serializer.data)


@api_view(["GET"])
def task_statistics(request):
    status_counts = {value: 0 for value, _ in STATUS_CHOICES}
    grouped_tasks = (
        Task.objects.values("status")
        .annotate(count=Count("pk"))
        .order_by("status")
    )
    for group in grouped_tasks:
        status_counts[group["status"]] = group["count"]

    overdue_tasks = Task.objects.filter(deadline__lt=timezone.now()).count()

    return Response(
        {
            "total_tasks": Task.objects.count(),
            "tasks_by_status": status_counts,
            "overdue_tasks": overdue_tasks,
        }
    )
```

При создании сериализатор проверяет входные поля; некорректные данные возвращают `400 Bad Request`, успешное создание — `201 Created`. Список сериализуется с `many=True`. Для отсутствующего ID `get_object_or_404` возвращает `404 Not Found`. Статистика группируется ORM-агрегацией `Count`; статусы без задач сохраняются с нулевым значением. Просроченной считается задача с дедлайном раньше текущего времени.

### Маршруты (`task_manager/urls.py`)

```python
from django.urls import path

from . import views


urlpatterns = [
    path("tasks/", views.task_list, name="task-list"),
    path("tasks/create/", views.task_create, name="task-create"),
    path("tasks/statistics/", views.task_statistics, name="task-statistics"),
    path("tasks/<int:pk>/", views.task_detail, name="task-detail"),
]
```

В `config/urls.py` маршруты приложения подключаются префиксом `api/`.


### Скриншоты ручного тестирования

Запросы выполнены через `curl` из интегрированного терминала VS Code. На снимках
видны соответствующие маршруты, успешные HTTP-статусы и данные ответов.

1. Создание задачи — `201 Created`: [скриншот](task_manager_api/screenshots/01_create_task.jpg)
2. Список задач — `200 OK`: [скриншот](task_manager_api/screenshots/02_task_list.jpg)
3. Задача по ID — `200 OK`: [скриншот](task_manager_api/screenshots/03_task_detail.jpg)
4. Статистика — `200 OK`: [скриншот](task_manager_api/screenshots/04_task_statistics.jpg)
