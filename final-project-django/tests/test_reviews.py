"""Review API scenarios for confirmed stays, ownership and retained history."""

from datetime import datetime, timedelta
from datetime import timezone as utc_timezone
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.db import connection
from django.test import TestCase
from django.test.utils import CaptureQueriesContext
from django.utils import timezone
from drf_spectacular.generators import SchemaGenerator
from rest_framework.exceptions import ValidationError
from rest_framework.test import APIClient

from apps.bookings.models import Booking
from apps.listings.models import City, Listing
from apps.reviews.models import Review
from apps.reviews.services import create_review, update_review

User = get_user_model()


class ReviewAPITests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.owner = User.objects.create_user(
            email="review-owner-api@example.com",
            display_name="Owner",
            password="Test12345!safe",
        )
        cls.tenant = User.objects.create_user(
            email="review-tenant-api@example.com",
            display_name="Tenant",
            password="Test12345!safe",
        )
        cls.other = User.objects.create_user(
            email="review-other-api@example.com",
            display_name="Other",
            password="Test12345!safe",
        )
        cls.owner.groups.add(Group.objects.get(name="Landlord"))
        tenant_group = Group.objects.get(name="Tenant")
        cls.tenant.groups.add(tenant_group)
        cls.other.groups.add(tenant_group)
        cls.listing = Listing.objects.create(
            landlord=cls.owner,
            title="Review test apartment",
            description="Historic stays",
            city=City.objects.get(name="Hannover"),
            postal_code="30159",
            street="Street",
            house_number="5",
            housing_type="APARTMENT",
            rooms=2,
            price_per_night="80.00",
        )
        today = timezone.localdate()
        cls.completed = Booking.objects.create(
            listing=cls.listing,
            tenant=cls.tenant,
            check_in=today - timedelta(days=3),
            check_out=today,
            status=Booking.Status.CONFIRMED,
        )

    def setUp(self):
        self.client = APIClient()

    def auth(self, user):
        self.client.force_authenticate(user=user)

    def create(self, booking=None, *, rating=5, comment="Excellent stay", **extra):
        return self.client.post(
            "/api/reviews/",
            {
                "booking_id": (booking or self.completed).pk,
                "rating": rating,
                "comment": comment,
                **extra,
            },
            format="json",
        )

    def booking(
        self, *, tenant=None, status=Booking.Status.CONFIRMED, checkout_offset=0
    ):
        today = timezone.localdate()
        return Booking.objects.create(
            listing=self.listing,
            tenant=tenant or self.tenant,
            check_in=today - timedelta(days=5),
            check_out=today + timedelta(days=checkout_offset),
            status=status,
            cancelled_at=timezone.now() if status == Booking.Status.CANCELLED else None,
        )

    def test_direct_create_and_update_reject_whitespace_only_comments(self):
        for comment in (" ", "\t\n", "\u00a0"):
            with self.subTest(comment=comment):
                with self.assertRaises(ValidationError) as caught:
                    create_review(
                        actor=self.tenant,
                        booking_id=self.completed.pk,
                        rating=5,
                        comment=comment,
                    )
                self.assertIn("comment", caught.exception.detail)
        self.assertFalse(Review.objects.exists())
        review = create_review(
            actor=self.tenant, booking_id=self.completed.pk, rating=5, comment="Good"
        )
        for comment in (" ", "\t\n", "\u00a0"):
            with self.subTest(comment=comment):
                with self.assertRaises(ValidationError) as caught:
                    update_review(
                        actor=self.tenant,
                        review_id=review.pk,
                        changes={"comment": comment},
                    )
                self.assertIn("comment", caught.exception.detail)
                review.refresh_from_db()
                self.assertEqual(review.comment, "Good")
        updated = update_review(
            actor=self.tenant, review_id=review.pk, changes={"comment": "Better"}
        )
        self.assertEqual(updated.comment, "Better")

    def test_create_requires_auth_tenant_role_and_booking_owner(self):
        self.assertEqual(self.create().status_code, 401)
        self.auth(self.owner)
        self.assertEqual(self.create().status_code, 403)
        self.owner.groups.add(Group.objects.get(name="Tenant"))
        self.assertEqual(self.create().status_code, 404)
        self.auth(self.other)
        self.assertEqual(self.create().status_code, 404)
        self.auth(self.tenant)
        self.assertEqual(
            self.client.post(
                "/api/reviews/",
                {"booking_id": 99999999, "rating": 5, "comment": "No booking"},
            ).status_code,
            404,
        )
        self.assertFalse(Review.objects.exists())

    def test_confirmed_checkout_today_allows_review_without_client_spoof(self):
        self.auth(self.tenant)
        response = self.create(tenant_id=self.owner.pk, listing_id=9999)
        self.assertEqual(response.status_code, 201, response.data)
        self.assertEqual(response.data["booking_id"], self.completed.pk)
        self.assertEqual(response.data["tenant_id"], self.tenant.pk)
        self.assertEqual(response.data["listing_id"], self.listing.pk)
        self.assertEqual(response.data["rating"], 5)
        self.assertNotIn("email", response.data)
        self.assertEqual(Review.objects.count(), 1)

    def test_nonconfirmed_and_future_stays_are_rejected(self):
        self.auth(self.tenant)
        for booking in (
            self.booking(status=Booking.Status.PENDING),
            self.booking(status=Booking.Status.REJECTED),
            self.booking(status=Booking.Status.CANCELLED),
            self.booking(checkout_offset=1),
        ):
            with self.subTest(status=booking.status, check_out=booking.check_out):
                response = self.create(booking)
                self.assertEqual(response.status_code, 400, response.data)
                self.assertIn("booking", response.data)
        self.assertFalse(Review.objects.exists())

    def test_rating_comment_and_booking_id_validation(self):
        self.auth(self.tenant)
        for rating in (0, 6, -1, "not a number", None):
            with self.subTest(rating=rating):
                self.assertEqual(self.create(rating=rating).status_code, 400)
        for comment in ("", "   ", None):
            with self.subTest(comment=comment):
                self.assertEqual(self.create(comment=comment).status_code, 400)
        self.assertEqual(
            self.client.post(
                "/api/reviews/", {"rating": 5, "comment": "Missing booking"}
            ).status_code,
            400,
        )
        self.assertFalse(Review.objects.exists())

    def test_duplicate_returns_conflict_and_separate_stays_allow_more_reviews(self):
        self.auth(self.tenant)
        self.assertEqual(self.create().status_code, 201)
        self.assertEqual(self.create().status_code, 409)
        another = self.booking()
        self.assertEqual(self.create(another, rating=3).status_code, 201)
        self.assertEqual(Review.objects.count(), 2)

    def test_only_author_may_patch_and_immutable_booking_is_not_changed(self):
        self.auth(self.tenant)
        created = self.create()
        self.assertEqual(created.status_code, 201, created.data)
        review_id = created.data["id"]
        self.auth(self.other)
        self.assertEqual(
            self.client.patch(f"/api/reviews/{review_id}/", {"rating": 1}).status_code,
            404,
        )
        self.auth(self.owner)
        self.assertEqual(
            self.client.patch(f"/api/reviews/{review_id}/", {"rating": 1}).status_code,
            404,
        )
        self.auth(self.tenant)
        edited = self.client.patch(
            f"/api/reviews/{review_id}/",
            {
                "rating": 4,
                "comment": "Updated",
                "booking_id": 999999,
                "tenant_id": self.other.pk,
            },
        )
        self.assertEqual(edited.status_code, 200, edited.data)
        review = Review.objects.get(pk=review_id)
        self.assertEqual(review.booking_id, self.completed.pk)
        self.assertEqual(review.rating, 4)
        self.assertEqual(review.comment, "Updated")

    def test_invalid_update_does_not_modify_review_and_delete_is_disallowed(self):
        self.auth(self.tenant)
        created = self.create()
        review_id = created.data["id"]
        self.assertEqual(
            self.client.patch(f"/api/reviews/{review_id}/", {"rating": 7}).status_code,
            400,
        )
        self.assertEqual(
            self.client.patch(
                f"/api/reviews/{review_id}/", {"comment": " "}
            ).status_code,
            400,
        )
        self.assertEqual(
            self.client.put(
                f"/api/reviews/{review_id}/", {"rating": 1, "comment": "rewrite"}
            ).status_code,
            405,
        )
        self.assertEqual(
            self.client.delete(f"/api/reviews/{review_id}/").status_code, 405
        )
        self.assertEqual(Review.objects.get(pk=review_id).rating, 5)
        self.assertEqual(Review.objects.get(pk=review_id).comment, "Excellent stay")

    def test_listing_reviews_public_and_aggregate_average(self):
        Review.objects.create(booking=self.completed, rating=3, comment="Fine")
        second = self.booking(tenant=self.other)
        Review.objects.create(booking=second, rating=5, comment="Great")
        response = self.client.get(f"/api/listings/{self.listing.pk}/reviews/")
        self.assertEqual(response.status_code, 200, response.data)
        self.assertEqual(response.data["count"], 2)
        self.assertEqual(response.data["review_count"], 2)
        self.assertEqual(float(response.data["average_rating"]), 4.0)
        self.assertEqual(
            {entry["rating"] for entry in response.data["results"]}, {3, 5}
        )
        for entry in response.data["results"]:
            self.assertNotIn("tenant_id", entry)
            self.assertNotIn("booking_id", entry)

    def test_public_empty_listing_and_nonexisting_listing(self):
        response = self.client.get(f"/api/listings/{self.listing.pk}/reviews/")
        self.assertEqual(response.status_code, 200, response.data)
        self.assertEqual(response.data["review_count"], 0)
        self.assertIsNone(response.data["average_rating"])
        self.assertEqual(
            self.client.get("/api/listings/999999/reviews/").status_code, 404
        )

    def test_reviews_can_be_created_after_listing_soft_deletion(self):
        self.listing.is_active = False
        self.listing.deleted_at = timezone.now()
        self.listing.save(update_fields=["is_active", "deleted_at"])
        self.auth(self.tenant)
        response = self.create()
        self.assertEqual(response.status_code, 201, response.data)
        self.assertEqual(Review.objects.count(), 1)

    def test_inactive_and_deleted_reviews_readable_to_participants_only(self):
        review = Review.objects.create(
            booking=self.completed, rating=4, comment="The apartment"
        )
        listing_url = f"/api/listings/{self.listing.pk}/reviews/"
        detail_url = f"/api/reviews/{review.pk}/"
        self.assertEqual(self.client.get(listing_url).status_code, 200)
        public_detail = self.client.get(detail_url)
        self.assertEqual(public_detail.status_code, 200)
        self.assertNotIn("tenant_id", public_detail.data)
        self.assertNotIn("booking_id", public_detail.data)
        self.listing.is_active = False
        self.listing.save(update_fields=["is_active"])
        self.assertEqual(self.client.get(listing_url).status_code, 404)
        self.assertEqual(self.client.get(detail_url).status_code, 404)
        self.listing.deleted_at = timezone.now()
        self.listing.save(update_fields=["deleted_at"])
        self.auth(self.other)
        self.assertEqual(self.client.get(listing_url).status_code, 404)
        self.assertEqual(self.client.get(detail_url).status_code, 404)
        for participant in (self.tenant, self.owner):
            with self.subTest(participant=participant.pk):
                self.auth(participant)
                self.assertEqual(self.client.get(listing_url).status_code, 200)
                self.assertEqual(self.client.get(detail_url).status_code, 200)

    def test_review_detail_is_anonymous_only_for_public_listing(self):
        review = Review.objects.create(
            booking=self.completed, rating=5, comment="Wonderful"
        )
        detail_url = f"/api/reviews/{review.pk}/"
        self.assertEqual(self.client.get(detail_url).status_code, 200)
        self.assertEqual(self.client.get("/api/reviews/999999/").status_code, 404)
        self.assertEqual(self.client.get("/api/reviews/").status_code, 401)
        self.auth(self.tenant)
        self.assertEqual(self.client.get("/api/reviews/").status_code, 405)

    def test_status_change_after_review_prevents_invalid_edit(self):
        review = Review.objects.create(
            booking=self.completed, rating=4, comment="Before"
        )
        self.completed.status = Booking.Status.CANCELLED
        self.completed.cancelled_at = timezone.now()
        self.completed.save(update_fields=["status", "cancelled_at"])
        self.auth(self.tenant)
        result = self.client.patch(f"/api/reviews/{review.pk}/", {"comment": "After"})
        self.assertEqual(result.status_code, 400)
        review.refresh_from_db()
        self.assertEqual(review.comment, "Before")

    def test_berlin_calendar_checkout_at_utc_midnight(self):
        self.auth(self.tenant)
        utc_now = datetime(2026, 3, 28, 23, 30, tzinfo=utc_timezone.utc)
        with (
            timezone.override("Europe/Berlin"),
            patch("django.utils.timezone.now", return_value=utc_now),
        ):
            booking = Booking.objects.create(
                listing=self.listing,
                tenant=self.tenant,
                check_in=datetime(2026, 3, 25).date(),
                check_out=datetime(2026, 3, 29).date(),
                status=Booking.Status.CONFIRMED,
            )
            response = self.create(booking, comment="At Berlin checkout")
            self.assertEqual(response.status_code, 201, response.data)

    def test_openapi_lists_pagination_aggregates_and_private_fields(self):
        schema = SchemaGenerator().get_schema(public=True)
        paginated = schema["components"]["schemas"]["PaginatedReviewPublicList"]
        self.assertIn("review_count", paginated["properties"])
        self.assertIn("average_rating", paginated["properties"])
        public = schema["components"]["schemas"]["ReviewPublic"]
        self.assertNotIn("tenant_id", public["properties"])
        self.assertNotIn("booking_id", public["properties"])

    def test_pagination_rating_aggregate_and_no_n_plus_one(self):
        today = timezone.localdate()
        for index in range(23):
            booking = Booking.objects.create(
                listing=self.listing,
                tenant=self.tenant,
                check_in=today - timedelta(days=5),
                check_out=today,
                status=Booking.Status.CONFIRMED,
            )
            Review.objects.create(
                booking=booking, rating=(index % 5) + 1, comment="Review"
            )
        with CaptureQueriesContext(connection) as queries:
            response = self.client.get(f"/api/listings/{self.listing.pk}/reviews/")
        self.assertEqual(response.status_code, 200, response.data)
        self.assertEqual(response.data["count"], 23)
        self.assertEqual(response.data["review_count"], 23)
        self.assertEqual(len(response.data["results"]), 20)
        self.assertLessEqual(len(queries), 6)
