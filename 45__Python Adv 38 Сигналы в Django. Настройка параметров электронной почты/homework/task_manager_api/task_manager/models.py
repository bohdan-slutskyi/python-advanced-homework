from django.conf import settings
from django.db import models
from django.utils import timezone


STATUS_CHOICES = (
    ("new", "New"),
    ("in_progress", "In progress"),
    ("pending", "Pending"),
    ("blocked", "Blocked"),
    ("done", "Done"),
)


class CategoryQuerySet(models.QuerySet):
    def delete(self):
        count = self.filter(is_deleted=False).update(is_deleted=True, deleted_at=timezone.now())
        return count, {self.model._meta.label: count}


class ActiveCategoryManager(models.Manager.from_queryset(CategoryQuerySet)):
    def get_queryset(self):
        return super().get_queryset().filter(is_deleted=False)


class Category(models.Model):
    name = models.CharField(max_length=100, unique=True)
    is_deleted = models.BooleanField(default=False)
    deleted_at = models.DateTimeField(null=True, blank=True)
    objects = ActiveCategoryManager()
    all_objects = CategoryQuerySet.as_manager()

    def delete(self, using=None, keep_parents=False):
        if self.is_deleted:
            return 0, {self._meta.label: 0}
        self.is_deleted = True
        self.deleted_at = timezone.now()
        self.save(using=using, update_fields=("is_deleted", "deleted_at"))
        return 1, {self._meta.label: 1}

    def __str__(self) -> str:
        return self.name

    class Meta:
        db_table = "task_manager_category"
        ordering = ["name", "pk"]
        base_manager_name = "all_objects"
        default_manager_name = "objects"
        verbose_name = "Category"
        verbose_name_plural = "Categories"


class Task(models.Model):
    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="owned_tasks",
        null=True,
        blank=True,
    )
    title = models.CharField(max_length=200, unique=True)
    description = models.TextField()
    categories = models.ManyToManyField(
        Category,
        blank=True,
        related_name="tasks",
    )
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default="new",
    )
    deadline = models.DateTimeField()
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self) -> str:
        return self.title

    class Meta:
        db_table = "task_manager_task"
        ordering = ["-created_at"]
        verbose_name = "Task"
        verbose_name_plural = "Tasks"


class SubTask(models.Model):
    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="owned_subtasks",
        null=True,
        blank=True,
    )
    title = models.CharField(max_length=200, unique=True)
    description = models.TextField()
    task = models.ForeignKey(
        Task,
        on_delete=models.CASCADE,
        related_name="subtasks",
    )
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default="new",
    )
    deadline = models.DateTimeField()
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self) -> str:
        return self.title

    class Meta:
        db_table = "task_manager_subtask"
        ordering = ["-created_at"]
        verbose_name = "SubTask"
        verbose_name_plural = "SubTasks"


class RevokedAccessToken(models.Model):
    """Серверный blacklist для access JWT: jti и время истечения (не сам токен)."""

    jti = models.CharField(max_length=255, unique=True)
    expires_at = models.DateTimeField()
    revoked_at = models.DateTimeField(default=timezone.now)

    class Meta:
        ordering = ["-revoked_at"]

    def __str__(self):
        return f"Revoked access token (expires {self.expires_at.isoformat()})"
