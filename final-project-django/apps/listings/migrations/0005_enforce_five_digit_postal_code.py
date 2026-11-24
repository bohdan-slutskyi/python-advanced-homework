"""Reject malformed historical postcodes before tightening the schema."""

import re

import django.core.validators
from django.db import migrations, models


def preflight_postcodes(apps, schema_editor):
    Listing = apps.get_model("listings", "Listing")
    alias = schema_editor.connection.alias
    values = Listing.objects.using(alias).values_list("postal_code", flat=True)
    invalid = sum(
        not isinstance(value, str) or re.fullmatch(r"[0-9]{5}", value) is None
        for value in values.iterator()
    )
    if invalid:
        raise RuntimeError(
            f"{invalid} listing(s) have invalid postal codes; "
            "verify the original addresses before migrating."
        )


class Migration(migrations.Migration):
    dependencies = [("listings", "0004_normalize_geography")]

    operations = [
        migrations.RunPython(preflight_postcodes, migrations.RunPython.noop),
        migrations.AddConstraint(
            model_name="listing",
            constraint=models.CheckConstraint(
                condition=models.Q(postal_code__regex=r"^[0-9]{5}$")
                & ~models.Q(postal_code__regex=r"[^0-9]"),
                name="listing_postal_code_ascii_digits",
            ),
        ),
        migrations.AlterField(
            model_name="listing",
            name="postal_code",
            field=models.CharField(
                max_length=5,
                validators=[
                    django.core.validators.RegexValidator(
                        r"\A[0-9]{5}\Z", "A German postal code has five digits."
                    )
                ],
            ),
        ),
    ]
