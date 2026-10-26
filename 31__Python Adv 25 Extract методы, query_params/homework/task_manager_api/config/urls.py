"""URL configuration for the task manager project."""

from django.contrib import admin
from django.urls import include, path


urlpatterns = [
    path("admin/", admin.site.urls),
    path("api/", include("task_manager.urls")),
]
