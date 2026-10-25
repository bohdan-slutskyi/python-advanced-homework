from datetime import timedelta

from .models import SubTask, Task


TASK_TITLE = "Prepare presentation"
INFORMATION_TITLE = "Gather information"
SLIDES_TITLE = "Create slides"


def create_records(reference):
    # Не подменяем и не удаляем уже существующие записи с такими названиями.
    if Task.objects.filter(title=TASK_TITLE).exists() or SubTask.objects.filter(
        title__in=[INFORMATION_TITLE, SLIDES_TITLE],
    ).exists():
        raise ValueError("Записи с названиями упражнения уже существуют. Изменения не выполнены.")
    task = Task.objects.create(
        title=TASK_TITLE,
        description="Prepare materials and slides for the presentation",
        status="new",
        deadline=reference + timedelta(days=3),
    )
    information = SubTask.objects.create(
        title=INFORMATION_TITLE,
        description="Find necessary information for the presentation",
        status="new",
        deadline=reference + timedelta(days=2),
        task=task,
    )
    slides = SubTask.objects.create(
        title=SLIDES_TITLE,
        description="Create presentation slides",
        status="new",
        deadline=reference + timedelta(days=1),
        task=task,
    )
    return task, information, slides


def read_new_tasks():
    return Task.objects.filter(status="new").order_by("pk")


def read_overdue_done_subtasks(reference):
    return SubTask.objects.filter(status="done", deadline__lt=reference).order_by("pk")


def update_records(task, information, slides, reference):
    task.status = "in_progress"
    task.save(update_fields=["status"])
    information.deadline = reference - timedelta(days=2)
    information.save(update_fields=["deadline"])
    slides.description = "Create and format presentation slides"
    slides.save(update_fields=["description"])


def delete_records(task):
    # CASCADE удаляет связанные подзадачи; другие задачи не затрагиваются.
    return task.delete()
