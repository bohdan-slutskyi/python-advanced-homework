"""The model labels are lazy translations; machine values stay stable."""

from django.apps import apps
from django.test import SimpleTestCase
from django.utils.functional import Promise

from apps.bookings.models import Booking, BookingStatus
from apps.listings.models import City, CountryCode, HousingType, Listing


class LocalizedMetadataTests(SimpleTestCase):
    def test_project_model_and_declared_field_names_are_lazy(self):
        for label in ("accounts", "listings", "bookings", "reviews", "statistics"):
            for model in apps.get_app_config(label).get_models():
                with self.subTest(model=model.__name__):
                    self.assertIsInstance(model._meta.verbose_name, Promise)
                    self.assertIsInstance(model._meta.verbose_name_plural, Promise)
                    for field in model._meta.local_fields:
                        if field.auto_created or field.name in (
                            "password",
                            "last_login",
                            "is_superuser",
                        ):
                            continue
                        self.assertIsInstance(field.verbose_name, Promise, field.name)
        self.assertEqual(str(City._meta.verbose_name_plural), "cities")

    def test_choice_values_and_existing_public_aliases_are_unchanged(self):
        self.assertIs(Booking.Status, BookingStatus)
        self.assertIs(Listing.HousingType, HousingType)
        self.assertIs(Listing.CountryCode, CountryCode)
        self.assertEqual(
            Booking.Status.values, ["PENDING", "CONFIRMED", "REJECTED", "CANCELLED"]
        )
        self.assertEqual(
            Listing.HousingType.values, ["APARTMENT", "HOUSE", "STUDIO", "ROOM"]
        )
        self.assertEqual(Listing.CountryCode.values, ["DE"])
        for choices in (BookingStatus, HousingType, CountryCode):
            for member in choices:
                self.assertIsInstance(member.label, Promise)
