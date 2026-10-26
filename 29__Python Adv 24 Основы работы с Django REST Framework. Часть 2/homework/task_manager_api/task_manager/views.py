from django.db.models import Count
from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework.decorators import api_view

from .models import STATUS_CHOICES, SubTask, Task
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


@api_view(["GET"])
def task_list(request):
    serializer = TaskSerializer(Task.objects.all(), many=True)
    return Response(serializer.data)


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
        subtasks = SubTask.objects.select_related("task").all()
        return Response(SubTaskSerializer(subtasks, many=True).data)

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
