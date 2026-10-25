from django.urls import path

from . import views


urlpatterns = [
    path("tasks/", views.task_list, name="task-list"),
    path("tasks/create/", views.task_create, name="task-create"),
    path("tasks/statistics/", views.task_statistics, name="task-statistics"),
    path("tasks/<int:pk>/", views.task_detail, name="task-detail"),
]
