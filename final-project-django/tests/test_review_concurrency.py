"""Two real MySQL connections cannot create two reviews for one booking."""

from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta
from threading import Barrier
from unittest import skipUnless

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.db import connection, connections
from django.test import TransactionTestCase
from django.utils import timezone

from apps.bookings.models import Booking
from apps.listings.models import City, Listing
from apps.reviews.models import Review
from apps.reviews.services import ReviewConflict, create_review

User = get_user_model()


@skipUnless(connection.vendor == "mysql", "Concurrency acceptance needs MySQL")
class ReviewConcurrencyTests(TransactionTestCase):
    def setUp(self):
        self.owner = User.objects.create_user(
            email="race-review-owner@example.com",
            display_name="Owner",
            password="Test12345!safe",
        )
        self.tenant = User.objects.create_user(
            email="race-review-tenant@example.com",
            display_name="Tenant",
            password="Test12345!safe",
        )
        tenant_group, _ = Group.objects.get_or_create(name="Tenant")
        self.tenant.groups.add(tenant_group)
        listing = Listing.objects.create(
            landlord=self.owner,
            title="One reviewed stay",
            description="Concurrent reviews",
            city=City.objects.get_or_create(name="Hildesheim")[0],
            postal_code="31134",
            street="Street",
            house_number="8",
            housing_type="STUDIO",
            rooms=1,
            price_per_night="60.00",
        )
        today = timezone.localdate()
        self.booking = Booking.objects.create(
            listing=listing,
            tenant=self.tenant,
            check_in=today - timedelta(days=3),
            check_out=today - timedelta(days=1),
            status=Booking.Status.CONFIRMED,
        )

    def test_two_concurrent_reviews_only_one_is_saved(self):
        gate = Barrier(2)

        def create_in_thread(rating):
            try:
                connection.ensure_connection()
                mysql_thread_id = connection.connection.thread_id()
                gate.wait(timeout=10)
                try:
                    create_review(
                        actor=self.tenant,
                        booking_id=self.booking.pk,
                        rating=rating,
                        comment=f"Rating {rating}",
                    )
                    return mysql_thread_id, "created"
                except ReviewConflict:
                    return mysql_thread_id, "conflict"
            finally:
                connections.close_all()

        with ThreadPoolExecutor(max_workers=2) as pool:
            futures = [
                pool.submit(create_in_thread, 3),
                pool.submit(create_in_thread, 5),
            ]
            outcomes = [future.result(timeout=20) for future in futures]

        self.assertNotEqual(outcomes[0][0], outcomes[1][0])
        self.assertCountEqual(
            [status for _, status in outcomes], ["created", "conflict"]
        )
        self.assertEqual(Review.objects.filter(booking=self.booking).count(), 1)
