"""One retention window for histories, public rankings and manual cleanup."""

from datetime import timedelta

from django.db.models import Count, Q
from django.utils import timezone

RETENTION_DAYS = 90


def retention_cutoff(days=RETENTION_DAYS):
    return timezone.now() - timedelta(days=days)


def with_recent_view_count(queryset):
    # A filtered aggregate preserves listings with zero recent views.
    return queryset.annotate(
        view_count=Count(
            "view_events",
            filter=Q(view_events__created_at__gte=retention_cutoff()),
        )
    )
