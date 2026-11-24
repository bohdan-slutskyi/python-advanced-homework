"""Strengthen the cancellation invariant without inventing timestamps."""

from django.db import migrations, models
from django.db.models import Q


def preflight_cancellation(apps, schema_editor):
    Booking = apps.get_model("bookings", "Booking")
    alias = schema_editor.connection.alias
    invalid = Booking.objects.using(alias).filter(
        Q(status="CANCELLED", cancelled_at__isnull=True)
        | (~Q(status="CANCELLED") & Q(cancelled_at__isnull=False))
    )
    count = invalid.count()
    if count:
        raise RuntimeError(
            f"{count} booking(s) have inconsistent cancellation timestamps; "
            "verify historical cancellation records before migrating."
        )


class Migration(migrations.Migration):
    dependencies = [("bookings", "0004_price_and_cancelled_integrity")]

    operations = [
        migrations.RunPython(preflight_cancellation, migrations.RunPython.noop),
        migrations.AddConstraint(
            model_name="booking",
            constraint=models.CheckConstraint(
                condition=Q(status="CANCELLED", cancelled_at__isnull=False)
                | (~Q(status="CANCELLED") & Q(cancelled_at__isnull=True)),
                name="booking_cancelled_timestamp_matches",
            ),
        ),
        migrations.RemoveConstraint(
            model_name="booking",
            name="booking_cancelled_has_timestamp",
        ),
    ]
