from datetime import date, datetime, timedelta
from datetime import timezone as utc_timezone
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.db import IntegrityError, connection, transaction
from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient

from apps.bookings.models import Booking
from apps.listings.models import City, Listing
from apps.reviews.models import Review
from apps.statistics.models import SearchEvent

User = get_user_model()


class ModelReviewTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.owner = User.objects.create_user(
            email="review-owner@example.com",
            display_name="Owner",
            password="Strong-for-review-2026!",
        )
        cls.tenant = User.objects.create_user(
            email="review-guest@example.com",
            display_name="Guest",
            password="Strong-for-review-2026!",
        )
        cls.listing = Listing.objects.create(
            landlord=cls.owner,
            title="Test flat",
            description="Test description",
            city=City.objects.get(name="Hannover"),
            postal_code="30159",
            street="Test Street",
            house_number="10",
            housing_type=Listing.HousingType.STUDIO,
            rooms=1,
            price_per_night="49.00",
        )

    def booking(self, start, end, **kwargs):
        return Booking(
            listing=self.listing,
            tenant=self.tenant,
            check_in=start,
            check_out=end,
            **kwargs,
        )

    def test_booking_today_and_365_night_boundaries_valid(self):
        today = timezone.localdate()
        for check_in, check_out in (
            (today, today + timedelta(days=1)),
            (today, today + timedelta(days=365)),
            (today + timedelta(days=365), today + timedelta(days=366)),
        ):
            with self.subTest(check_in=check_in, check_out=check_out):
                self.booking(check_in, check_out).full_clean()

    def test_booking_rejects_past_and_future_horizon(self):
        today = timezone.localdate()
        for check_in, expected in (
            (today - timedelta(days=1), "check_in"),
            (today + timedelta(days=366), "check_in"),
        ):
            with self.subTest(check_in=check_in):
                with self.assertRaises(ValidationError) as caught:
                    self.booking(check_in, check_in + timedelta(days=1)).full_clean()
                self.assertIn(expected, caught.exception.message_dict)

    def test_booking_rejects_zero_negative_and_excess_duration(self):
        today = timezone.localdate()
        for end in (today, today - timedelta(days=1), today + timedelta(days=366)):
            with self.subTest(end=end):
                with self.assertRaises(ValidationError) as caught:
                    self.booking(today, end).full_clean()
                self.assertIn("check_out", caught.exception.message_dict)

    def test_booking_rejects_owner_even_with_tenant_group_and_inactive_listing(self):
        today = timezone.localdate()
        booking = Booking(
            listing=self.listing,
            tenant=self.owner,
            check_in=today + timedelta(days=1),
            check_out=today + timedelta(days=2),
        )
        with self.assertRaises(ValidationError) as caught:
            booking.full_clean()
        self.assertIn("tenant", caught.exception.message_dict)

        self.listing.is_active = False
        self.listing.save(update_fields=["is_active"])
        with self.assertRaises(ValidationError) as caught:
            self.booking(
                today + timedelta(days=1), today + timedelta(days=2)
            ).full_clean()
        self.assertIn("listing", caught.exception.message_dict)

    def test_booking_uses_berlin_calendar_day_at_utc_midnight(self):
        # 2026-03-28 23:30 UTC is 2026-03-29 00:30 in Berlin.
        utc_now = datetime(2026, 3, 28, 23, 30, tzinfo=utc_timezone.utc)
        with (
            timezone.override("Europe/Berlin"),
            patch("django.utils.timezone.now", return_value=utc_now),
        ):
            check_in = date(2026, 3, 28)
            with self.assertRaises(ValidationError) as caught:
                self.booking(check_in, check_in + timedelta(days=1)).full_clean()
            self.assertIn("check_in", caught.exception.message_dict)

    def test_review_only_confirmed_and_checkout_reached(self):
        today = timezone.localdate()
        booking = Booking.objects.create(
            listing=self.listing,
            tenant=self.tenant,
            check_in=today - timedelta(days=3),
            check_out=today - timedelta(days=1),
            status=Booking.Status.PENDING,
        )
        review = Review(booking=booking, rating=4, comment="Accurate description")
        with self.assertRaises(ValidationError) as caught:
            review.full_clean()
        self.assertIn("booking", caught.exception.message_dict)
        booking.status = Booking.Status.CONFIRMED
        booking.check_out = today + timedelta(days=1)
        booking.save(update_fields=["status", "check_out"])
        with self.assertRaises(ValidationError) as caught:
            review.full_clean()
        self.assertIn("booking", caught.exception.message_dict)
        booking.check_out = today
        booking.save(update_fields=["check_out"])
        review.full_clean()

    def test_listing_postal_code_validation_in_model_and_api(self):
        self.listing.postal_code = "3X159"
        with self.assertRaises(ValidationError) as caught:
            self.listing.full_clean()
        self.assertIn("postal_code", caught.exception.message_dict)
        from django.contrib.auth.models import Group

        self.owner.groups.add(Group.objects.get(name="Landlord"))
        client = APIClient()
        client.force_authenticate(self.owner)
        response = client.post(
            "/api/listings/",
            {
                "title": "Another flat",
                "description": "Another listing",
                "city": "Hannover",
                "postal_code": "3X159",
                "street": "Test Street",
                "house_number": "11",
                "housing_type": "STUDIO",
                "rooms": 1,
                "price_per_night": "49.00",
            },
        )
        self.assertEqual(response.status_code, 400)
        self.assertIn("postal_code", response.data)

    def test_database_rejects_invalid_choices_and_active_deleted_listing(self):
        for field, value in (
            ("country_code", "XX"),
            ("country_code", "de"),
            ("housing_type", "INVALID"),
            ("housing_type", "studio"),
        ):
            with self.subTest(field=field):
                with self.assertRaises(IntegrityError):
                    with transaction.atomic():
                        Listing.objects.filter(pk=self.listing.pk).update(
                            **{field: value}
                        )
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                Listing.objects.filter(pk=self.listing.pk).update(
                    deleted_at=timezone.now(), is_active=True
                )

        today = timezone.localdate()
        for status in ("INVALID", "pending", "PENDING "):
            with self.subTest(status=status):
                with self.assertRaises(IntegrityError):
                    with transaction.atomic():
                        Booking.objects.create(
                            listing=self.listing,
                            tenant=self.tenant,
                            check_in=today,
                            check_out=today + timedelta(days=1),
                            status=status,
                        )

    def test_search_event_normalized_and_nonempty(self):
        event = SearchEvent(query_text="   room   Hannover  ")
        event.full_clean()
        self.assertEqual(event.query_text, "room Hannover")
        with self.assertRaises(ValidationError) as caught:
            SearchEvent(query_text="   ").full_clean()
        self.assertIn("query_text", caught.exception.message_dict)
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                SearchEvent.objects.create(query_text="")

    def test_mysql_email_unique_case_insensitive(self):
        if connection.vendor != "mysql":
            self.skipTest("MySQL collation test")
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                User.objects.filter(pk=self.tenant.pk).update(
                    email=self.owner.email.upper()
                )

    def test_mysql_constraints_exist_in_introspection(self):
        if connection.vendor != "mysql":
            self.skipTest("SQL metadata acceptance is specific to MySQL")
        with connection.cursor() as cursor:
            listings = connection.introspection.get_constraints(
                cursor, "listings_listing"
            )
            bookings = connection.introspection.get_constraints(
                cursor, "bookings_booking"
            )
            reviews = connection.introspection.get_constraints(cursor, "reviews_review")
        for constraint in (
            "listing_rooms_gt_zero",
            "listing_price_gt_zero",
            "listing_country_de",
            "listing_housing_type",
            "listing_deleted_inactive",
        ):
            self.assertIn(constraint, listings)
            self.assertTrue(listings[constraint]["check"])
        for constraint in ("booking_dates_valid", "booking_status_allowed"):
            self.assertIn(constraint, bookings)
            self.assertTrue(bookings[constraint]["check"])
        self.assertTrue(reviews["review_rating_1_to_5"]["check"])
