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
    status_counts = {status: 0 for status, _ in STATUS_CHOICES}
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
