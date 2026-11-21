"""Persist booking quotes; never fabricate old prices from current listing rates."""

from django.db import migrations, models
from django.db.models import Q


def preflight_cancelled_rows(apps, schema_editor):
    Booking = apps.get_model("bookings", "Booking")
    bad = Booking.objects.using(schema_editor.connection.alias).filter(
        status="CANCELLED", cancelled_at__isnull=True
    )
    if bad.exists():
        raise RuntimeError(
            "Existing CANCELLED bookings have no cancelled_at; "
            "repair timestamps from trusted audit records before migrating."
        )


class Migration(migrations.Migration):
    dependencies = [("bookings", "0003_alter_booking_status")]

    operations = [
        migrations.RunPython(preflight_cancelled_rows, migrations.RunPython.noop),
        migrations.AddField(
            model_name="booking",
            name="total_price",
            field=models.DecimalField(
                max_digits=13, decimal_places=2, null=True, blank=True
            ),
        ),
        migrations.AddConstraint(
            model_name="booking",
            constraint=models.CheckConstraint(
                condition=~Q(status="CANCELLED") | Q(cancelled_at__isnull=False),
                name="booking_cancelled_has_timestamp",
            ),
        ),
        migrations.AddConstraint(
            model_name="booking",
            constraint=models.CheckConstraint(
                condition=Q(total_price__gt=0) | Q(total_price__isnull=True),
                name="booking_total_price_positive",
            ),
        ),
    ]
