from django.urls import path
from . import views

urlpatterns = [
    path("tasks/", views.TaskListCreateView.as_view(), name="task-list"),
    path("tasks/create/", views.TaskListCreateView.as_view(), name="task-create"),
    path("tasks/statistics/", views.task_statistics, name="task-statistics"),
    path("tasks/<int:pk>/", views.TaskDetailUpdateDeleteView.as_view(), name="task-detail"),
    path("subtasks/", views.SubTaskListCreateView.as_view(), name="subtask-list-create"),
    path("subtasks/<int:pk>/", views.SubTaskDetailUpdateDeleteView.as_view(), name="subtask-detail-update-delete"),
]
