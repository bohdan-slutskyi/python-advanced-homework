from django.contrib import admin, messages
from django.db.models import QuerySet
from django.http import HttpRequest

from .models import Category, SubTask, Task


class SubTaskInline(admin.TabularInline):
    model = SubTask
    extra = 1
    fields = ("title", "description", "status", "deadline")


@admin.register(Task)
class TaskAdmin(admin.ModelAdmin):
    list_display = ("short_title", "status", "deadline", "created_at")
    search_fields = ("title", "description")
    list_filter = ("status", "categories", "created_at")
    ordering = ("-created_at",)
    readonly_fields = ("created_at",)
    filter_horizontal = ("categories",)
    inlines = (SubTaskInline,)

    @admin.display(description="title", ordering="title")
    def short_title(self, obj: Task) -> str:
        if len(obj.title) > 10:
            return f"{obj.title[:10]}..."
        return obj.title


@admin.action(description="Mark selected subtasks as Done")
def mark_subtasks_done(
    modeladmin: admin.ModelAdmin,
    request: HttpRequest,
    queryset: QuerySet[SubTask],
) -> None:
    updated_count = queryset.update(status="done")
    modeladmin.message_user(
        request,
        f"{updated_count} subtask(s) marked as Done.",
        messages.SUCCESS,
    )


@admin.register(SubTask)
class SubTaskAdmin(admin.ModelAdmin):
    list_display = ("title", "task", "status", "deadline", "created_at")
    search_fields = ("title", "description", "task__title")
    list_filter = ("status", "created_at")
    ordering = ("-created_at",)
    readonly_fields = ("created_at",)
    list_select_related = ("task",)
    actions = (mark_subtasks_done,)


@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    list_display = ("name",)
    search_fields = ("name",)
    ordering = ("name",)
