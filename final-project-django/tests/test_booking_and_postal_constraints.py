"""Strict postal-code and bidirectional cancellation invariants."""

from datetime import timedelta
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.core.exceptions import ValidationError
from django.db import DataError, IntegrityError, connection, transaction
from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient

from apps.bookings.models import Booking
from apps.listings.models import City, Listing


class BookingAndPostalConstraintsTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        user_model = get_user_model()
        cls.owner = user_model.objects.create_user(
            email="postal-owner@example.invalid", display_name="Owner"
        )
        cls.tenant = user_model.objects.create_user(
            email="postal-tenant@example.invalid", display_name="Tenant"
        )
        cls.owner.groups.add(Group.objects.get(name="Landlord"))
        cls.tenant.groups.add(Group.objects.get(name="Tenant"))
        cls.city = City.objects.get(name="Berlin")
        cls.listing = Listing.objects.create(
            landlord=cls.owner,
            title="Postal code regression",
            description="Test",
            city=cls.city,
            postal_code="01234",
            street="Test street",
            house_number="1",
            housing_type=Listing.HousingType.STUDIO,
            rooms=1,
            price_per_night=Decimal("25.00"),
        )
        start = timezone.localdate() + timedelta(days=5)
        cls.booking = Booking.objects.create(
            listing=cls.listing,
            tenant=cls.tenant,
            check_in=start,
            check_out=start + timedelta(days=2),
            total_price=Decimal("50.00"),
        )

    def setUp(self):
        self.client = APIClient()
        self.client.force_authenticate(self.owner)
        self.url = f"/api/listings/{self.listing.pk}/"

    def test_model_and_database_allow_only_matching_cancelled_timestamp(self):
        timestamp = timezone.now()
        for status in Booking.Status.values:
            for cancelled_at in (None, timestamp):
                valid = (status == Booking.Status.CANCELLED) == (
                    cancelled_at is not None
                )
                with self.subTest(
                    status=status, has_timestamp=cancelled_at is not None
                ):
                    self.booking.status = status
                    self.booking.cancelled_at = cancelled_at
                    if valid:
                        self.booking.full_clean()
                        Booking.objects.filter(pk=self.booking.pk).update(
                            status=status, cancelled_at=cancelled_at
                        )
                        self.booking.refresh_from_db()
                        self.assertEqual(self.booking.status, status)
                        self.assertEqual(
                            self.booking.cancelled_at is not None,
                            cancelled_at is not None,
                        )
                    else:
                        with self.assertRaises(ValidationError):
                            self.booking.full_clean()
                        with self.assertRaises(IntegrityError), transaction.atomic():
                            Booking.objects.filter(pk=self.booking.pk).update(
                                status=status, cancelled_at=cancelled_at
                            )

    def test_cancellation_api_sets_timestamp_without_losing_price(self):
        self.client.force_authenticate(self.tenant)
        response = self.client.post(f"/api/bookings/{self.booking.pk}/cancel/")
        self.assertEqual(response.status_code, 200, response.data)
        self.booking.refresh_from_db()
        self.assertEqual(self.booking.status, Booking.Status.CANCELLED)
        self.assertIsNotNone(self.booking.cancelled_at)
        self.assertEqual(self.booking.total_price, Decimal("50.00"))

    def test_postal_code_model_rejects_non_ascii_or_inexact_lengths(self):
        for value in (
            "1234",
            "123456",
            "12A45",
            "１２３４５",
            "١٢٣٤٥",
            "01234\n",
            " 1234",
            "1234 ",
            "",
            "0123\n",
        ):
            with self.subTest(value=value):
                self.listing.postal_code = value
                with self.assertRaises(ValidationError) as caught:
                    self.listing.full_clean()
                self.assertIn("postal_code", caught.exception.message_dict)
        self.listing.postal_code = "01234"
        self.listing.full_clean()

    def test_postal_code_api_rejects_bad_values_without_trimming(self):
        for value in (
            "1234",
            "123456",
            "12A45",
            "１２３４５",
            "١٢٣٤٥",
            "01234\n",
            " 1234",
            "1234 ",
            "",
            None,
            "0123\n",
        ):
            with self.subTest(value=value):
                result = self.client.patch(
                    self.url, {"postal_code": value}, format="json"
                )
                self.assertEqual(result.status_code, 400, result.data)
                self.assertIn("postal_code", result.data)
                self.listing.refresh_from_db()
                self.assertEqual(self.listing.postal_code, "01234")
        result = self.client.patch(self.url, {"postal_code": "00123"}, format="json")
        self.assertEqual(result.status_code, 200, result.data)
        self.assertEqual(result.data["postal_code"], "00123")
        self.listing.refresh_from_db()
        self.assertEqual(self.listing.postal_code, "00123")

    def test_database_rejects_bad_postal_codes_without_model_validation(self):
        for value in (
            "1234",
            "123456",
            "12A45",
            "１２３４５",
            "١٢٣٤٥",
            " 1234",
            "1234 ",
            "",
            "0123\n",
        ):
            with self.subTest(value=value):
                with (
                    self.assertRaises((IntegrityError, DataError)),
                    transaction.atomic(),
                ):
                    Listing.objects.filter(pk=self.listing.pk).update(postal_code=value)
                self.listing.refresh_from_db()
                self.assertEqual(self.listing.postal_code, "01234")
        Listing.objects.filter(pk=self.listing.pk).update(postal_code="00123")
        self.listing.refresh_from_db()
        self.assertEqual(self.listing.postal_code, "00123")

    def test_database_never_persists_overlength_trailing_newline(self):
        # MySQL can truncate trailing whitespace to VARCHAR width before CHECK.
        # The API/model reject the input; the DB must never store malformed data.
        value = "54321\n"
        try:
            with transaction.atomic():
                Listing.objects.filter(pk=self.listing.pk).update(postal_code=value)
                if connection.vendor == "mysql":
                    with connection.cursor() as cursor:
                        cursor.execute("SHOW WARNINGS")
                        self.assertTrue(
                            any(row[1] in (1265, 1406) for row in cursor.fetchall()),
                            "A silent truncation is not acceptable.",
                        )
        except IntegrityError, DataError:
            expected = "01234"
        else:
            expected = "54321"
        self.listing.refresh_from_db()
        self.assertEqual(self.listing.postal_code, expected)
