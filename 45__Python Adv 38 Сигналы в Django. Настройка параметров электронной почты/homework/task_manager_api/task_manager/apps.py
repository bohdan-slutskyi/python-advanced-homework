from django.apps import AppConfig


class TaskManagerConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "task_manager"
    verbose_name = "Менеджер задач"

    def ready(self):
        # Регистрация обработчиков изменений основных задач.
        from . import signals  # noqa: F401
