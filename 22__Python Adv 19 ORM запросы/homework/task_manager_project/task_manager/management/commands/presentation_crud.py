from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.utils import timezone

from task_manager.models import SubTask, Task
from task_manager.presentation_queries import (
    create_records, delete_records, read_new_tasks, read_overdue_done_subtasks, update_records,
)


class Command(BaseCommand):
    help = "Выполняет четыре этапа CRUD для задачи Prepare presentation."

    def print_record(self, obj):
        self.stdout.write(f"{obj.title} | status={obj.get_status_display()} | deadline={obj.deadline.isoformat()}")
        self.stdout.write(f"description={obj.description}")

    def handle(self, *args, **options):
        reference = timezone.now()
        self.stdout.write(f"REFERENCE (UTC): {reference.isoformat()}")
        try:
            with transaction.atomic():
                self.stdout.write("1. CREATE")
                task, information, slides = create_records(reference)
                for obj in (task, information, slides):
                    self.print_record(obj)
                task_id = task.pk
                subtask_ids = [information.pk, slides.pk]

                self.stdout.write("2. READ")
                self.stdout.write(f"Tasks, New: {list(read_new_tasks().values_list('title', flat=True))}")
                self.stdout.write(f"SubTasks, Done and overdue: {list(read_overdue_done_subtasks(reference).values_list('title', flat=True))}")

                self.stdout.write("3. UPDATE")
                update_records(task, information, slides, reference)
                # Сверяем отображаемые значения с сохранёнными данными.
                for obj in (task, information, slides):
                    obj.refresh_from_db()
                    self.print_record(obj)

                self.stdout.write("4. DELETE")
                total, by_model = delete_records(task)
                self.stdout.write(f"Deleted total={total}; by model={by_model}")
                remaining_tasks = Task.objects.filter(pk=task_id).count()
                remaining_subtasks = SubTask.objects.filter(pk__in=subtask_ids).count()
                self.stdout.write(f"Remaining exercise records: Task={remaining_tasks}, SubTask={remaining_subtasks}")
        except ValueError as error:
            raise CommandError(str(error)) from error
        self.stdout.write(self.style.SUCCESS("CRUD completed successfully."))
