"""Real InnoDB race: separate connections contend on the same Listing row."""

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
from apps.bookings.services import BookingConflict, confirm_booking
from apps.listings.models import City, Listing

User = get_user_model()


@skipUnless(connection.vendor == "mysql", "Concurrency acceptance needs real MySQL")
class BookingConcurrencyTests(TransactionTestCase):
    def setUp(self):
        self.owner = User.objects.create_user(
            email="race-owner@example.com",
            display_name="Owner",
            password="Test12345!safe",
        )
        self.owner.groups.add(Group.objects.get_or_create(name="Landlord")[0])
        first = User.objects.create_user(
            email="race-first@example.com",
            display_name="First",
            password="Test12345!safe",
        )
        second = User.objects.create_user(
            email="race-second@example.com",
            display_name="Second",
            password="Test12345!safe",
        )
        self.listing = Listing.objects.create(
            landlord=self.owner,
            title="One calendar",
            description="InnoDB booking test",
            city=City.objects.get_or_create(name="Hildesheim")[0],
            postal_code="31134",
            street="Street",
            house_number="2",
            housing_type="STUDIO",
            rooms=1,
            price_per_night="70.00",
        )
        start = timezone.localdate() + timedelta(days=20)
        self.first = Booking.objects.create(
            listing=self.listing,
            tenant=first,
            check_in=start,
            check_out=start + timedelta(days=5),
        )
        self.second = Booking.objects.create(
            listing=self.listing,
            tenant=second,
            check_in=start + timedelta(days=2),
            check_out=start + timedelta(days=6),
        )

    def test_parallel_confirmations_use_distinct_mysql_connections(self):
        gate = Barrier(2)

        def try_confirm(booking_id):
            # Django connection objects are thread-local; both requests use
            # separate transactions, not the outer rollback of TestCase.
            try:
                connection.ensure_connection()
                mysql_thread = connection.connection.thread_id()
                gate.wait(timeout=10)
                try:
                    confirm_booking(booking_id=booking_id, actor=self.owner)
                    return mysql_thread, "confirmed"
                except BookingConflict:
                    return mysql_thread, "conflict"
            finally:
                connections.close_all()

        with ThreadPoolExecutor(max_workers=2) as pool:
            futures = [
                pool.submit(try_confirm, self.first.pk),
                pool.submit(try_confirm, self.second.pk),
            ]
            outcomes = [future.result(timeout=20) for future in futures]

        self.assertNotEqual(outcomes[0][0], outcomes[1][0])
        self.assertCountEqual(
            [value for _, value in outcomes], ["confirmed", "conflict"]
        )
        self.assertEqual(
            Booking.objects.filter(
                listing=self.listing, status=Booking.Status.CONFIRMED
            ).count(),
            1,
        )
        self.assertEqual(
            Booking.objects.filter(
                listing=self.listing, status=Booking.Status.PENDING
            ).count(),
            1,
        )
