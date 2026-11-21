"""Regression tests for geography, booking prices, and database constraints (MySQL)."""

from datetime import timedelta
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient

from apps.bookings.models import MAX_ADVANCE_BOOKING_DAYS, MAX_STAY_NIGHTS, Booking
from apps.listings.models import City, District, Listing
from apps.reviews.models import Review


class ModelIntegrityTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        User = get_user_model()
        cls.owner = User.objects.create_user(
            email="model-owner@example.invalid",
            display_name="Landlord",
            password="Tests-Only-Strong-Password",
        )
        cls.tenant = User.objects.create_user(
            email="model-tenant@example.invalid",
            display_name="Tenant",
            password="Tests-Only-Strong-Password",
        )
        cls.owner.groups.add(Group.objects.get(name="Landlord"))
        cls.tenant.groups.add(Group.objects.get(name="Tenant"))
        cls.berlin = City.objects.get(name="Berlin")
        cls.hannover = City.objects.get(name="Hannover")
        cls.mitte_berlin = District.objects.get(city=cls.berlin, name="Mitte")
        cls.mitte_hannover = District.objects.get(city=cls.hannover, name="Mitte")

    def setUp(self):
        self.client = APIClient()
        self.payload = {
            "title": "Location and price test",
            "description": "Model integrity",
            "city": "Berlin",
            "district": "Mitte",
            "postal_code": "10115",
            "street": "Example Str.",
            "house_number": "1",
            "housing_type": "STUDIO",
            "rooms": 1,
            "price_per_night": "12.35",
        }

    def create_listing(self):
        self.client.force_authenticate(self.owner)
        response = self.client.post("/api/listings/", self.payload, format="json")
        self.assertEqual(response.status_code, 201, response.data)
        return Listing.objects.get(pk=response.data["id"])

    def test_city_district_fk_and_string_api_compatibility(self):
        listing = self.create_listing()
        self.assertEqual(listing.city_id, self.berlin.pk)
        self.assertEqual(listing.district_id, self.mitte_berlin.pk)
        self.assertEqual(listing.legacy_city, "")
        self.client.force_authenticate(user=None)
        result = self.client.get(
            "/api/listings/", {"city": "bErLiN", "district": "mItTe"}
        )
        self.assertEqual(result.data["count"], 1)
        self.assertEqual(result.data["results"][0]["city"], "Berlin")
        self.assertEqual(result.data["results"][0]["district"], "Mitte")
        self.assertNotIn("legacy_city", result.data["results"][0])

    def test_city_scoped_districts_and_unique_names(self):
        self.assertNotEqual(self.mitte_berlin.pk, self.mitte_hannover.pk)
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                City.objects.create(name="BERLIN")
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                District.objects.create(city=self.berlin, name="MITTE")
        listing = Listing(
            landlord=self.owner,
            title="Wrong district",
            description="Invalid city-scoped relationship",
            city=self.berlin,
            district=self.mitte_hannover,
            postal_code="10115",
            street="Example",
            house_number="1",
            housing_type="STUDIO",
            rooms=1,
            price_per_night=Decimal("25.00"),
        )
        with self.assertRaises(ValidationError) as error:
            listing.full_clean()
        self.assertIn("district", error.exception.message_dict)

    def test_bad_geography_is_rejected_and_city_change_requires_district(self):
        self.client.force_authenticate(self.owner)
        for patch in (
            {"city": "Unrecognized Municipality"},
            {"district": "Not A Real District"},
            {"city": "Hannover", "district": "Kreuzberg"},
        ):
            response = self.client.post(
                "/api/listings/", {**self.payload, **patch}, format="json"
            )
            self.assertEqual(response.status_code, 400, response.data)
        listing = self.create_listing()
        response = self.client.patch(
            f"/api/listings/{listing.pk}/", {"city": "Hannover"}, format="json"
        )
        self.assertEqual(response.status_code, 400)
        response = self.client.patch(
            f"/api/listings/{listing.pk}/",
            {"city": "Hannover", "district": ""},
            format="json",
        )
        self.assertEqual(response.status_code, 200, response.data)
        listing.refresh_from_db()
        self.assertEqual(listing.city, self.hannover)
        self.assertIsNone(listing.district_id)
        self.assertEqual(response.data["district"], "")

    def test_price_snapshot_survives_listing_price_change_and_confirmation(self):
        listing = self.create_listing()
        start = timezone.localdate() + timedelta(days=10)
        self.client.force_authenticate(self.tenant)
        booking_response = self.client.post(
            "/api/bookings/",
            {
                "listing_id": listing.pk,
                "check_in": start.isoformat(),
                "check_out": (start + timedelta(days=3)).isoformat(),
            },
        )
        self.assertEqual(booking_response.status_code, 201, booking_response.data)
        self.assertEqual(booking_response.data["total_price"], "37.05")
        booking_id = booking_response.data["id"]
        self.client.force_authenticate(self.owner)
        self.assertEqual(
            self.client.patch(
                f"/api/listings/{listing.pk}/",
                {"price_per_night": "20.00"},
                format="json",
            ).status_code,
            200,
        )
        response = self.client.post(f"/api/bookings/{booking_id}/confirm/")
        self.assertEqual(response.status_code, 200, response.data)
        self.assertEqual(response.data["total_price"], "37.05")
        self.client.force_authenticate(self.tenant)
        response = self.client.get(f"/api/bookings/{booking_id}/")
        self.assertEqual(response.data["total_price"], "37.05")
        another = self.client.post(
            "/api/bookings/",
            {
                "listing_id": listing.pk,
                "check_in": (start + timedelta(days=5)).isoformat(),
                "check_out": (start + timedelta(days=8)).isoformat(),
            },
        )
        self.assertEqual(another.status_code, 201, another.data)
        self.assertEqual(another.data["total_price"], "60.00")
        self.assertEqual(
            Booking.objects.get(pk=booking_id).total_price, Decimal("37.05")
        )

    def test_mysql_check_rejects_cancelled_without_timestamp(self):
        listing = self.create_listing()
        start = timezone.localdate() + timedelta(days=10)
        booking = Booking.objects.create(
            listing=listing,
            tenant=self.tenant,
            check_in=start,
            check_out=start + timedelta(days=1),
            total_price=Decimal("12.35"),
        )
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                Booking.objects.filter(pk=booking.pk).update(status="CANCELLED")
        booking.refresh_from_db()
        self.assertEqual(booking.status, Booking.Status.PENDING)
        booking.status = Booking.Status.CANCELLED
        with self.assertRaises(ValidationError):
            booking.full_clean()
        self.client.force_authenticate(self.tenant)
        response = self.client.post(f"/api/bookings/{booking.pk}/cancel/")
        self.assertEqual(response.status_code, 200, response.data)
        self.assertIsNotNone(response.data["cancelled_at"])
        self.assertEqual(response.data["total_price"], "12.35")

    def test_named_booking_limits_and_str_methods(self):
        self.assertEqual(MAX_STAY_NIGHTS, 365)
        self.assertEqual(MAX_ADVANCE_BOOKING_DAYS, 365)
        listing = self.create_listing()
        start = timezone.localdate() + timedelta(days=1)
        booking = Booking(
            listing=listing,
            tenant=self.tenant,
            check_in=start,
            check_out=start + timedelta(days=MAX_STAY_NIGHTS),
            total_price=Decimal("4507.75"),
        )
        booking.full_clean()
        booking.check_out += timedelta(days=1)
        with self.assertRaises(ValidationError) as error:
            booking.full_clean()
        self.assertIn("check_out", error.exception.message_dict)
        booking.check_in = start + timedelta(days=MAX_ADVANCE_BOOKING_DAYS + 1)
        booking.check_out = booking.check_in + timedelta(days=1)
        with self.assertRaises(ValidationError) as error:
            booking.full_clean()
        self.assertIn("check_in", error.exception.message_dict)
        booking.check_in = start
        booking.check_out = start + timedelta(days=1)
        booking.save()
        review = Review(booking=booking, rating=5, comment="Good")
        self.assertIn(f"Booking #{booking.pk}", str(booking))
        self.assertIn(f"listing #{listing.pk}", str(booking))
        self.assertNotIn("example.invalid", str(booking))
        self.assertIn(f"booking #{booking.pk}", str(review))
        self.assertIn("5/5", str(review))
