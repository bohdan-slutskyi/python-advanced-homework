from django_filters import rest_framework as filters
from .models import STATUS_CHOICES, SubTask, Task


class TaskFilter(filters.FilterSet):
    status = filters.ChoiceFilter(choices=STATUS_CHOICES)
    deadline = filters.IsoDateTimeFilter()

    class Meta:
        model = Task
        fields = ["status", "deadline"]


class SubTaskFilter(filters.FilterSet):
    status = filters.ChoiceFilter(choices=STATUS_CHOICES)
    deadline = filters.IsoDateTimeFilter()
    task_title = filters.CharFilter(field_name="task__title", lookup_expr="exact")

    class Meta:
        model = SubTask
        fields = ["status", "deadline", "task_title"]
