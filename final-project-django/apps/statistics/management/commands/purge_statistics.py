"""Purge only expired interaction events; preserve rental history and content."""

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from apps.statistics.models import SearchEvent, ViewEvent
from apps.statistics.retention import RETENTION_DAYS, retention_cutoff


class Command(BaseCommand):
    help = "Preview expired SearchEvent/ViewEvent deletions (apply explicitly)."

    def add_arguments(self, parser):
        parser.add_argument("--days", type=int, default=RETENTION_DAYS)
        parser.add_argument("--batch-size", type=int, default=1000)
        parser.add_argument(
            "--apply", action="store_true", help="Actually remove expired events."
        )

    def handle(self, *args, **options):
        days = options["days"]
        batch_size = options["batch_size"]
        if days < 1 or batch_size < 1:
            raise CommandError("--days and --batch-size must be positive integers.")
        cutoff = retention_cutoff(days)
        counts = {}
        for model in (SearchEvent, ViewEvent):
            expired = model.objects.filter(created_at__lt=cutoff)
            before = expired.count()
            counts[model.__name__] = before
            if options["apply"]:
                while True:
                    ids = list(
                        model.objects.filter(created_at__lt=cutoff)
                        .order_by("created_at", "pk")
                        .values_list("pk", flat=True)[:batch_size]
                    )
                    if not ids:
                        break
                    with transaction.atomic():
                        model.objects.filter(pk__in=ids, created_at__lt=cutoff).delete()
        mode = "deleted" if options["apply"] else "would delete"
        self.stdout.write(
            f"Before {cutoff.isoformat()} ({days} days): "
            + ", ".join(f"{model}={count} {mode}" for model, count in counts.items())
        )
