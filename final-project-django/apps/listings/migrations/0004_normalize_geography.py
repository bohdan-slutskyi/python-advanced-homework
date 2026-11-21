"""Normalize active geography while retaining exact original labels for audits."""

import django.db.models.deletion
from django.db import migrations, models

# Explicitly curated cities and city-scoped districts; no Faker place names.
CITIES = ("Berlin", "Hamburg", "Hannover", "Köln", "Hildesheim", "Bonn")
DISTRICTS = {
    "Berlin": ("Mitte", "Kreuzberg"),
    "Hannover": ("Mitte", "List"),
}


def populate_geography(apps, schema_editor):
    City = apps.get_model("listings", "City")
    District = apps.get_model("listings", "District")
    Listing = apps.get_model("listings", "Listing")
    alias = schema_editor.connection.alias
    cities = {
        name.casefold(): City.objects.using(alias).get_or_create(name=name)[0]
        for name in CITIES
    }
    districts = {}
    for city_name, names in DISTRICTS.items():
        city = cities[city_name.casefold()]
        for name in names:
            district = District.objects.using(alias).get_or_create(
                city=city, name=name
            )[0]
            districts[(city_name.casefold(), name.casefold())] = district
    for listing in Listing.objects.using(alias).all().iterator():
        city_key = listing.legacy_city.strip().casefold()
        if city_key not in cities:
            # No automatic "correction" of unknown/misspelled municipality.
            raise RuntimeError(
                f"Listing {listing.pk} has unverified city: "
                "curate City catalogue and retry migration."
            )
        district = districts.get((city_key, listing.legacy_district.strip().casefold()))
        Listing.objects.using(alias).filter(pk=listing.pk).update(
            city_id=cities[city_key].pk,
            district_id=district.pk if district else None,
        )


def recover_legacy_labels(apps, schema_editor):
    City = apps.get_model("listings", "City")
    District = apps.get_model("listings", "District")
    Listing = apps.get_model("listings", "Listing")
    alias = schema_editor.connection.alias
    cities = dict(City.objects.using(alias).values_list("pk", "name"))
    districts = dict(District.objects.using(alias).values_list("pk", "name"))
    for listing in Listing.objects.using(alias).all().iterator():
        Listing.objects.using(alias).filter(pk=listing.pk).update(
            legacy_city=listing.legacy_city or cities.get(listing.city_id, ""),
            legacy_district=listing.legacy_district
            or districts.get(listing.district_id, ""),
        )


class Migration(migrations.Migration):
    dependencies = [("listings", "0003_alter_listing_country_code_and_more")]

    operations = [
        migrations.RemoveIndex(model_name="listing", name="listing_city_district_idx"),
        migrations.RenameField(
            model_name="listing", old_name="city", new_name="legacy_city"
        ),
        migrations.RenameField(
            model_name="listing", old_name="district", new_name="legacy_district"
        ),
        migrations.CreateModel(
            name="City",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                ("name", models.CharField(max_length=120, unique=True)),
            ],
            options={"ordering": ["name"]},
        ),
        migrations.CreateModel(
            name="District",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                ("name", models.CharField(max_length=120)),
                (
                    "city",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="districts",
                        to="listings.city",
                    ),
                ),
            ],
            options={"ordering": ["city_id", "name"]},
        ),
        migrations.AddConstraint(
            model_name="district",
            constraint=models.UniqueConstraint(
                fields=["city", "name"], name="district_city_name_uq"
            ),
        ),
        migrations.AddField(
            model_name="listing",
            name="city",
            field=models.ForeignKey(
                null=True,
                on_delete=django.db.models.deletion.PROTECT,
                related_name="listings",
                to="listings.city",
            ),
        ),
        migrations.AddField(
            model_name="listing",
            name="district",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.PROTECT,
                related_name="listings",
                to="listings.district",
            ),
        ),
        migrations.RunPython(populate_geography, recover_legacy_labels),
        migrations.AlterField(
            model_name="listing",
            name="city",
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.PROTECT,
                related_name="listings",
                to="listings.city",
            ),
        ),
        migrations.AlterField(
            model_name="listing",
            name="legacy_city",
            field=models.CharField(
                blank=True, default="", editable=False, max_length=120
            ),
        ),
        migrations.AlterField(
            model_name="listing",
            name="legacy_district",
            field=models.CharField(
                blank=True, default="", editable=False, max_length=120
            ),
        ),
        migrations.AddIndex(
            model_name="listing",
            index=models.Index(
                fields=["city", "district"], name="listing_city_district_idx"
            ),
        ),
    ]
