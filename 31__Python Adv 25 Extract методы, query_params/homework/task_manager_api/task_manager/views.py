from django.db.models import Count
from django.db.models.functions import ExtractWeekDay
from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework import status
from rest_framework.exceptions import ValidationError
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework.decorators import api_view

from .models import STATUS_CHOICES, SubTask, Task
from .pagination import SubTaskPagination
from .serializers import (
    SubTaskCreateSerializer,
    SubTaskSerializer,
    TaskCreateSerializer,
    TaskDetailSerializer,
    TaskSerializer,
)


@api_view(["POST"])
def task_create(request):
    serializer = TaskCreateSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)
    task = serializer.save()
    return Response(TaskDetailSerializer(task).data, status=status.HTTP_201_CREATED)


WEEKDAYS = {
    "воскресенье": 1, "sunday": 1,
    "понедельник": 2, "monday": 2,
    "вторник": 3, "tuesday": 3,
    "среда": 4, "wednesday": 4,
    "четверг": 5, "thursday": 5,
    "пятница": 6, "friday": 6,
    "суббота": 7, "saturday": 7,
}


@api_view(["GET"])
def task_list(request):
    tasks = Task.objects.order_by("-created_at", "-pk")
    weekday = request.query_params.get("weekday")
    if weekday is not None:
        value = weekday.strip().lower()
        # В ExtractWeekDay воскресенье — 1, понедельник — 2, вторник — 3.
        number = WEEKDAYS.get(value)
        if number is None and value in {"1", "2", "3", "4", "5", "6", "7"}:
            number = int(value)
        if number is None:
            raise ValidationError({"weekday": "Укажите название дня недели или число от 1 до 7."})
        tasks = tasks.annotate(deadline_weekday=ExtractWeekDay("deadline")).filter(
            deadline_weekday=number
        )
    return Response(TaskSerializer(tasks, many=True).data)


@api_view(["GET"])
def task_detail(request, pk: int):
    task = get_object_or_404(Task.objects.prefetch_related("subtasks"), pk=pk)
    return Response(TaskDetailSerializer(task).data)


@api_view(["GET"])
def task_statistics(request):
    status_counts = {choice: 0 for choice, _ in STATUS_CHOICES}
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


class SubTaskListCreateView(APIView):
    def get(self, request):
        subtasks = SubTask.objects.select_related("task").order_by("-created_at", "-pk")
        task_title = request.query_params.get("task_title")
        subtask_status = request.query_params.get("status")
        if task_title is not None:
            subtasks = subtasks.filter(task__title=task_title)
        if subtask_status is not None:
            if subtask_status not in dict(STATUS_CHOICES):
                raise ValidationError({"status": "Неизвестный статус подзадачи."})
            subtasks = subtasks.filter(status=subtask_status)

        # В APIView пагинация вызывается явно после применения фильтров.
        paginator = SubTaskPagination()
        page = paginator.paginate_queryset(subtasks, request, view=self)
        return paginator.get_paginated_response(SubTaskSerializer(page, many=True).data)

    def post(self, request):
        serializer = SubTaskCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        subtask = serializer.save()
        return Response(
            SubTaskSerializer(subtask).data,
            status=status.HTTP_201_CREATED,
        )


class SubTaskDetailUpdateDeleteView(APIView):
    def get_object(self, pk):
        return get_object_or_404(
            SubTask.objects.select_related("task"),
            pk=pk,
        )

    def get(self, request, pk: int):
        return Response(SubTaskSerializer(self.get_object(pk)).data)

    def put(self, request, pk: int):
        subtask = self.get_object(pk)
        serializer = SubTaskCreateSerializer(subtask, data=request.data)
        serializer.is_valid(raise_exception=True)
        return Response(SubTaskSerializer(serializer.save()).data)

    def patch(self, request, pk: int):
        subtask = self.get_object(pk)
        serializer = SubTaskCreateSerializer(
            subtask,
            data=request.data,
            partial=True,
        )
        serializer.is_valid(raise_exception=True)
        return Response(SubTaskSerializer(serializer.save()).data)

    def delete(self, request, pk: int):
        self.get_object(pk).delete()
        return Response(status=status.HTTP_204_NO_CONTENT)
