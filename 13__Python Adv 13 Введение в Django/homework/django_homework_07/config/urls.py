"""URL configuration for the homework project."""

from django.contrib import admin
from django.urls import include, path


urlpatterns = [
    path("admin/", admin.site.urls),
    path("", include("first_app.urls")),
]
