from django.contrib import admin

from .models import Category, SubTask, Task


@admin.register(Task)
class TaskAdmin(admin.ModelAdmin):
    list_display = ("title", "status", "deadline", "created_at")
    search_fields = ("title", "description")
    list_filter = ("status", "categories", "created_at")
    ordering = ("-created_at",)
    readonly_fields = ("created_at",)
    filter_horizontal = ("categories",)


@admin.register(SubTask)
class SubTaskAdmin(admin.ModelAdmin):
    list_display = ("title", "task", "status", "deadline", "created_at")
    search_fields = ("title", "description", "task__title")
    list_filter = ("status", "created_at")
    ordering = ("-created_at",)
    readonly_fields = ("created_at",)
    list_select_related = ("task",)


@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    list_display = ("name",)
    search_fields = ("name",)
    ordering = ("name",)
