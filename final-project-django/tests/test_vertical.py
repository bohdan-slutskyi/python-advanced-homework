from datetime import date, timedelta

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.db import IntegrityError, transaction
from django.db.models.deletion import ProtectedError
from django.test import TestCase
from rest_framework.test import APIClient

from apps.bookings.models import Booking
from apps.listings.models import Listing
from apps.reviews.models import Review

User = get_user_model()
PASSWORD = "SecureTest-Pass2026!"
LISTING = {
    "title": "Sunny flat",
    "description": "Near station",
    "city": "Hannover",
    "district": "Mitte",
    "postal_code": "30159",
    "street": "Teststraße",
    "house_number": "12",
    "housing_type": "STUDIO",
    "rooms": 1,
    "price_per_night": "72.50",
}


class AccountAPITests(TestCase):
    def setUp(self):
        self.client = APIClient()

    def register(self, email="tenant@example.com", **extra):
        return self.client.post(
            "/api/auth/register/",
            {
                "email": email,
                "display_name": "Tenant",
                "password": PASSWORD,
                **extra,
            },
        )

    def test_registration_email_groups_password_and_duplicate(self):
        response = self.register("Mixed@EXAMPLE.COM")
        self.assertEqual(response.status_code, 201, response.data)
        user = User.objects.get(pk=response.data["id"])
        self.assertEqual(user.email, "mixed@example.com")
        self.assertTrue(user.check_password(PASSWORD))
        self.assertNotIn("password", response.data)
        self.assertEqual(list(user.groups.values_list("name", flat=True)), ["Tenant"])
        self.assertEqual(self.register("MIXED@example.com").status_code, 400)

    def test_no_public_promotion_and_weak_password(self):
        self.assertEqual(
            self.register("weak@example.com", password="123").status_code, 400
        )
        response = self.register(groups=["Landlord"], is_staff=True)
        self.assertEqual(response.status_code, 201)
        user = User.objects.get(pk=response.data["id"])
        self.assertFalse(user.is_staff)
        self.assertFalse(user.groups.filter(name="Landlord").exists())
        user.groups.add(Group.objects.get(name="Landlord"))
        self.assertCountEqual(
            user.groups.values_list("name", flat=True), ["Tenant", "Landlord"]
        )

    def test_login_logout_own_refresh_blacklist_and_access_lifetime(self):
        self.assertEqual(self.register().status_code, 201)
        login = self.client.post(
            "/api/auth/login/",
            {
                "email": "tenant@example.com",
                "password": PASSWORD,
            },
        )
        self.assertEqual(login.status_code, 200, login.data)
        self.assertIn("refresh", login.data)
        self.assertIn("access", login.data)
        self.assertEqual(self.client.get("/api/auth/me/").status_code, 401)
        self.client.credentials(HTTP_AUTHORIZATION="Bearer " + login.data["access"])
        self.assertEqual(self.client.get("/api/auth/me/").status_code, 200)

        other = User.objects.create_user(
            email="other@example.com", display_name="Other", password=PASSWORD
        )
        other_login = self.client.post(
            "/api/auth/login/",
            {
                "email": other.email,
                "password": PASSWORD,
            },
        )
        self.assertEqual(other_login.status_code, 200)
        self.assertEqual(
            self.client.post(
                "/api/auth/logout/", {"refresh": other_login.data["refresh"]}
            ).status_code,
            400,
        )
        self.assertEqual(
            self.client.post(
                "/api/auth/logout/", {"refresh": login.data["refresh"]}
            ).status_code,
            204,
        )
        self.assertEqual(
            self.client.post(
                "/api/auth/logout/", {"refresh": login.data["refresh"]}
            ).status_code,
            400,
        )
        # A blacklisted refresh doesn't instantly revoke an already issued access JWT.
        self.assertEqual(self.client.get("/api/auth/me/").status_code, 200)


class ListingsAPITests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.owner = User.objects.create_user(
            email="owner@example.com", display_name="Owner", password=PASSWORD
        )
        self.other = User.objects.create_user(
            email="other-landlord@example.com", display_name="Other", password=PASSWORD
        )
        self.tenant = User.objects.create_user(
            email="tenant@example.com", display_name="Tenant", password=PASSWORD
        )
        group = Group.objects.get(name="Landlord")
        self.owner.groups.add(group)
        self.other.groups.add(group)

    def test_only_landlord_creates_and_cannot_spoof_owner(self):
        self.assertEqual(self.client.post("/api/listings/", LISTING).status_code, 401)
        self.client.force_authenticate(self.tenant)
        self.assertEqual(self.client.post("/api/listings/", LISTING).status_code, 403)
        self.client.force_authenticate(self.owner)
        response = self.client.post(
            "/api/listings/",
            {
                **LISTING,
                "landlord_id": self.tenant.pk,
                "country_code": "XX",
            },
        )
        self.assertEqual(response.status_code, 201, response.data)
        self.assertEqual(response.data["landlord_id"], self.owner.pk)
        self.assertEqual(response.data["country_code"], "DE")

    def test_owner_edit_hide_soft_delete_and_public_visibility(self):
        self.client.force_authenticate(self.owner)
        created = self.client.post("/api/listings/", LISTING)
        self.assertEqual(created.status_code, 201, created.data)
        path = f"/api/listings/{created.data['id']}/"
        self.client.force_authenticate(self.other)
        self.assertIn(
            self.client.patch(path, {"title": "Hijacked"}).status_code, (403, 404)
        )
        self.assertIn(self.client.delete(path).status_code, (403, 404))
        self.client.force_authenticate(self.owner)
        self.assertEqual(self.client.patch(path, {"is_active": False}).status_code, 200)
        self.client.force_authenticate(user=None)
        self.assertEqual(self.client.get("/api/listings/").data["count"], 0)
        self.assertEqual(self.client.get(path).status_code, 404)
        self.client.force_authenticate(self.owner)
        self.assertEqual(self.client.get(path).status_code, 200)
        self.assertEqual(self.client.patch(path, {"is_active": True}).status_code, 200)
        self.assertEqual(self.client.delete(path).status_code, 204)
        stored = Listing.objects.get(pk=created.data["id"])
        self.assertIsNotNone(stored.deleted_at)
        self.assertFalse(stored.is_active)
        self.assertEqual(self.client.get(path).status_code, 404)

    def test_soft_delete_preserves_booking_and_review_history(self):
        self.client.force_authenticate(self.owner)
        response = self.client.post("/api/listings/", LISTING)
        self.assertEqual(response.status_code, 201)
        listing = Listing.objects.get(pk=response.data["id"])
        booking = Booking.objects.create(
            listing=listing,
            tenant=self.tenant,
            check_in=date.today() - timedelta(days=4),
            check_out=date.today() - timedelta(days=2),
            status=Booking.Status.CONFIRMED,
        )
        review = Review.objects.create(booking=booking, rating=5, comment="Stayed here")
        self.assertEqual(
            self.client.delete(f"/api/listings/{listing.pk}/").status_code, 204
        )
        self.assertTrue(
            Booking.objects.filter(pk=booking.pk, listing_id=listing.pk).exists()
        )
        self.assertTrue(
            Review.objects.filter(pk=review.pk, booking_id=booking.pk).exists()
        )
        self.assertIsNotNone(Listing.objects.get(pk=listing.pk).deleted_at)

    def test_bad_values_rejected_by_api_and_database(self):
        self.client.force_authenticate(self.owner)
        for changes in (
            {"rooms": 0},
            {"price_per_night": "-1.00"},
            {"housing_type": "X"},
        ):
            response = self.client.post("/api/listings/", {**LISTING, **changes})
            self.assertEqual(response.status_code, 400, response.data)
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                Listing.objects.create(landlord=self.owner, **{**LISTING, "rooms": 0})


class OpenAPITests(TestCase):
    def test_schema_and_docs_are_served(self):
        client = APIClient()
        response = client.get("/api/schema/")
        self.assertEqual(response.status_code, 200)
        self.assertIn("openapi", response.data)
        self.assertIn("/api/listings/", response.data["paths"])
        self.assertIn("/api/auth/register/", response.data["paths"])
        self.assertEqual(client.get("/api/docs/").status_code, 200)


class SchemaTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.owner = User.objects.create_user(
            email="schema-owner@example.com",
            display_name="Owner",
            password=PASSWORD,
        )
        cls.tenant = User.objects.create_user(
            email="schema-guest@example.com",
            display_name="Guest",
            password=PASSWORD,
        )
        cls.listing = Listing.objects.create(landlord=cls.owner, **LISTING)

    def test_booking_date_check_is_database_constraint(self):
        today = date.today()
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                Booking.objects.create(
                    tenant=self.tenant,
                    listing=self.listing,
                    check_in=today + timedelta(days=3),
                    check_out=today + timedelta(days=2),
                )

    def test_review_rating_check_unique_booking_and_history_fk(self):
        booking = Booking.objects.create(
            tenant=self.tenant,
            listing=self.listing,
            check_in=date.today(),
            check_out=date.today() + timedelta(days=1),
        )
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                Review.objects.create(booking=booking, rating=6, comment="Invalid")
        Review.objects.create(booking=booking, rating=5, comment="Nice")
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                Review.objects.create(booking=booking, rating=3, comment="Duplicate")
        with self.assertRaises(ProtectedError):
            self.listing.delete()
        with self.assertRaises(ProtectedError):
            self.tenant.delete()
        self.assertTrue(Booking.objects.filter(pk=booking.pk).exists())
