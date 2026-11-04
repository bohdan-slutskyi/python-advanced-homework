from django.urls import include, path
from rest_framework.routers import DefaultRouter
from . import views

router = DefaultRouter()
router.register("categories", views.CategoryViewSet, basename="category")

urlpatterns = [
    path("", include(router.urls)),
    path("tasks/", views.TaskListCreateView.as_view(), name="task-list"),
    path("tasks/create/", views.TaskListCreateView.as_view(), name="task-create"),
    path("tasks/statistics/", views.task_statistics, name="task-statistics"),
    path("tasks/<int:pk>/", views.TaskDetailUpdateDeleteView.as_view(), name="task-detail"),
    path("subtasks/", views.SubTaskListCreateView.as_view(), name="subtask-list-create"),
    path("subtasks/<int:pk>/", views.SubTaskDetailUpdateDeleteView.as_view(), name="subtask-detail-update-delete"),
]
