from django.db.models import Count
from django.db.models.functions import ExtractWeekDay
from django.utils import timezone
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework import filters, generics, viewsets
from rest_framework.decorators import api_view, action
from rest_framework.exceptions import ValidationError
from rest_framework.response import Response

from .filters import SubTaskFilter, TaskFilter
from .models import STATUS_CHOICES, Category, SubTask, Task
from .pagination import SubTaskPagination
from .serializers import CategorySerializer, SubTaskCreateSerializer, SubTaskSerializer, TaskCreateSerializer, TaskDetailSerializer


WEEKDAYS = {
    "воскресенье": 1, "sunday": 1,
    "понедельник": 2, "monday": 2,
    "вторник": 3, "tuesday": 3,
    "среда": 4, "wednesday": 4,
    "четверг": 5, "thursday": 5,
    "пятница": 6, "friday": 6,
    "суббота": 7, "saturday": 7,
}



class CreatedAtOrderingFilter(filters.OrderingFilter):
    def get_ordering(self, request, queryset, view):
        ordering = super().get_ordering(request, queryset, view)
        # PK задаёт устойчивый порядок для совпадающего времени создания.
        return [*ordering, "-pk" if ordering[0].startswith("-") else "pk"]


class TaskListCreateView(generics.ListCreateAPIView):
    queryset = Task.objects.prefetch_related("subtasks", "categories")
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, CreatedAtOrderingFilter]
    filterset_class = TaskFilter
    search_fields = ["title", "description"]
    ordering_fields = ["created_at"]
    ordering = ["-created_at", "-pk"]

    def get_serializer_class(self):
        return TaskDetailSerializer if self.request.method == "GET" else TaskCreateSerializer

    def get_queryset(self):
        tasks = super().get_queryset()
        weekday = self.request.query_params.get("weekday")
        if weekday is not None:
            value = weekday.strip().lower()
            number = WEEKDAYS.get(value)
            if number is None and value in {"1", "2", "3", "4", "5", "6", "7"}:
                number = int(value)
            if number is None:
                raise ValidationError({"weekday": "Укажите название дня недели или число от 1 до 7."})
            tasks = tasks.annotate(deadline_weekday=ExtractWeekDay("deadline")).filter(deadline_weekday=number)
        return tasks


class TaskDetailUpdateDeleteView(generics.RetrieveUpdateDestroyAPIView):
    queryset = Task.objects.prefetch_related("subtasks", "categories")

    def get_serializer_class(self):
        return TaskDetailSerializer if self.request.method == "GET" else TaskCreateSerializer


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



class SubTaskListCreateView(generics.ListCreateAPIView):
    queryset = SubTask.objects.select_related("task")
    pagination_class = SubTaskPagination
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, CreatedAtOrderingFilter]
    filterset_class = SubTaskFilter
    search_fields = ["title", "description"]
    ordering_fields = ["created_at"]
    ordering = ["-created_at", "-pk"]

    def get_serializer_class(self):
        return SubTaskSerializer if self.request.method == "GET" else SubTaskCreateSerializer


class SubTaskDetailUpdateDeleteView(generics.RetrieveUpdateDestroyAPIView):
    queryset = SubTask.objects.select_related("task")

    def get_serializer_class(self):
        return SubTaskSerializer if self.request.method == "GET" else SubTaskCreateSerializer


class CategoryViewSet(viewsets.ModelViewSet):
    queryset = Category.objects.annotate(tasks_count=Count("tasks", distinct=True))
    serializer_class = CategorySerializer

    @action(detail=False, methods=["get"], url_path="count-tasks")
    def count_tasks(self, request):
        categories = self.get_queryset()
        return Response(list(categories.values("id", "name", "tasks_count")))

    @action(detail=True, methods=["get"], url_path="count-tasks")
    def category_tasks_count(self, request, pk=None):
        category = self.get_object()
        return Response({"id": category.pk, "name": category.name, "tasks_count": category.tasks_count})
