from django.db import models

STATUS_CHOICES = (
    ("new", "New"),
    ("in_progress", "In progress"),
    ("pending", "Pending"),
    ("blocked", "Blocked"),
    ("done", "Done"),
)


class Category(models.Model):
    name = models.CharField(max_length=100, unique=True)

    def __str__(self):
        return self.name

    class Meta:
        verbose_name = "Категория"
        verbose_name_plural = "Категории"


class Task(models.Model):
    title = models.CharField(max_length=200, unique_for_date="created_at")
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

    def __str__(self):
        return self.title

    class Meta:
        verbose_name = "Задача"
        verbose_name_plural = "Задачи"


class SubTask(models.Model):
    title = models.CharField(max_length=200)
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

    def __str__(self):
        return self.title

    class Meta:
        verbose_name = "Подзадача"
        verbose_name_plural = "Подзадачи"
