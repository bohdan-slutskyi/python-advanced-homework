"""Booking endpoints: scope, permission, date and lifecycle contracts."""

from datetime import timedelta

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient

from apps.bookings.models import Booking
from apps.listings.models import City, Listing

User = get_user_model()


class BookingAPITests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.owner = User.objects.create_user(
            email="booking-owner@example.com",
            display_name="Owner",
            password="Test12345!safe",
        )
        cls.other_owner = User.objects.create_user(
            email="booking-other-owner@example.com",
            display_name="Other Owner",
            password="Test12345!safe",
        )
        cls.tenant = User.objects.create_user(
            email="booking-tenant@example.com",
            display_name="Tenant",
            password="Test12345!safe",
        )
        cls.other_tenant = User.objects.create_user(
            email="booking-other-tenant@example.com",
            display_name="Other Tenant",
            password="Test12345!safe",
        )
        landlord = Group.objects.get(name="Landlord")
        tenant = Group.objects.get(name="Tenant")
        cls.owner.groups.add(landlord)
        cls.other_owner.groups.add(landlord)
        cls.tenant.groups.add(tenant)
        cls.other_tenant.groups.add(tenant)
        cls.listing = Listing.objects.create(
            landlord=cls.owner,
            title="Booking test flat",
            description="Description",
            city=City.objects.get(name="Hannover"),
            postal_code="30159",
            street="Street",
            house_number="1",
            housing_type="STUDIO",
            rooms=1,
            price_per_night="60.00",
        )

    def setUp(self):
        self.client = APIClient()
        self.start = timezone.localdate() + timedelta(days=10)
        self.end = self.start + timedelta(days=4)

    def auth(self, user):
        self.client.force_authenticate(user=user)

    def create(self, *, check_in=None, check_out=None, listing_id=None, **extra):
        return self.client.post(
            "/api/bookings/",
            {
                "listing_id": self.listing.pk if listing_id is None else listing_id,
                "check_in": (check_in or self.start).isoformat(),
                "check_out": (check_out or self.end).isoformat(),
                **extra,
            },
        )

    def pending(self, tenant=None, start=None, end=None, listing=None):
        return Booking.objects.create(
            listing=listing or self.listing,
            tenant=tenant or self.tenant,
            check_in=start or self.start,
            check_out=end or self.end,
        )

    def test_authentication_tenant_group_and_dual_role_self_booking(self):
        self.assertEqual(self.create().status_code, 401)
        self.auth(self.owner)
        self.assertEqual(self.create().status_code, 403)
        self.owner.groups.add(Group.objects.get(name="Tenant"))
        self.assertEqual(self.create().status_code, 403)
        self.auth(self.other_owner)
        self.assertEqual(self.create().status_code, 403)
        self.auth(self.tenant)
        self.assertEqual(self.create().status_code, 201)

    def test_create_sets_pending_and_ignores_client_owned_fields(self):
        self.auth(self.tenant)
        response = self.create(status="CONFIRMED", tenant_id=self.other_tenant.pk)
        self.assertEqual(response.status_code, 201, response.data)
        self.assertEqual(response.data["status"], Booking.Status.PENDING)
        self.assertEqual(response.data["tenant_id"], self.tenant.pk)
        self.assertEqual(response.data["listing_id"], self.listing.pk)
        self.assertEqual(
            Booking.objects.get(pk=response.data["id"]).status, Booking.Status.PENDING
        )
        self.assertIsNone(response.data["cancelled_at"])

    def test_date_model_validation_is_executed_before_save(self):
        self.auth(self.tenant)
        today = timezone.localdate()
        invalid = (
            (today - timedelta(days=1), today + timedelta(days=2)),
            (today, today + timedelta(days=1)),
            (self.start, self.start),
            (self.start, self.start - timedelta(days=1)),
            (today + timedelta(days=366), today + timedelta(days=367)),
            (today, today + timedelta(days=366)),
        )
        for check_in, check_out in invalid:
            with self.subTest(check_in=check_in, check_out=check_out):
                response = self.create(check_in=check_in, check_out=check_out)
                self.assertEqual(response.status_code, 400, response.data)
        self.assertEqual(Booking.objects.count(), 0)

    def test_dates_tomorrow_365_nights_and_horizon_boundary(self):
        self.auth(self.tenant)
        today = timezone.localdate()
        self.assertEqual(
            self.create(
                check_in=today + timedelta(days=1),
                check_out=today + timedelta(days=366),
            ).status_code,
            201,
        )
        self.assertEqual(
            self.create(
                check_in=today + timedelta(days=365),
                check_out=today + timedelta(days=366),
            ).status_code,
            201,
        )

    def test_bad_payload_and_missing_listing(self):
        self.auth(self.tenant)
        self.assertEqual(self.create(listing_id=987654321).status_code, 404)
        self.assertEqual(
            self.client.post(
                "/api/bookings/",
                {
                    "listing_id": self.listing.pk,
                    "check_in": "nonsense",
                    "check_out": "2026-01-01",
                },
            ).status_code,
            400,
        )
        self.assertEqual(
            self.client.post(
                "/api/bookings/",
                {"listing_id": self.listing.pk, "check_in": "2026-01-01"},
            ).status_code,
            400,
        )

    def test_disabled_and_deleted_listings_cannot_be_booked(self):
        self.auth(self.tenant)
        self.listing.is_active = False
        self.listing.save(update_fields=["is_active"])
        self.assertEqual(self.create().status_code, 409)
        self.listing.deleted_at = timezone.now()
        self.listing.save(update_fields=["deleted_at"])
        self.assertEqual(self.create().status_code, 404)

    def test_confirmed_dates_block_new_requests_but_not_adjacent_ones(self):
        confirmed = self.pending()
        confirmed.status = Booking.Status.CONFIRMED
        confirmed.save(update_fields=["status"])
        self.auth(self.other_tenant)
        self.assertEqual(self.create().status_code, 409)
        self.assertEqual(
            self.create(
                check_in=self.end, check_out=self.end + timedelta(days=1)
            ).status_code,
            201,
        )

    def test_pending_overlap_allowed_only_confirmed_blocks(self):
        self.auth(self.tenant)
        first = self.create()
        self.assertEqual(first.status_code, 201, first.data)
        self.auth(self.other_tenant)
        second = self.create(
            check_in=self.start + timedelta(days=1),
            check_out=self.end + timedelta(days=1),
        )
        self.assertEqual(second.status_code, 201, second.data)
        self.auth(self.owner)
        confirm = self.client.post(f"/api/bookings/{first.data['id']}/confirm/")
        self.assertEqual(confirm.status_code, 200, confirm.data)
        conflict = self.client.post(f"/api/bookings/{second.data['id']}/confirm/")
        self.assertEqual(conflict.status_code, 409, conflict.data)
        self.assertEqual(
            Booking.objects.get(pk=second.data["id"]).status, Booking.Status.PENDING
        )

    def test_adjacent_intervals_can_both_be_confirmed(self):
        first = self.pending()
        second = self.pending(
            tenant=self.other_tenant, start=self.end, end=self.end + timedelta(days=2)
        )
        self.auth(self.owner)
        self.assertEqual(
            self.client.post(f"/api/bookings/{first.pk}/confirm/").status_code, 200
        )
        self.assertEqual(
            self.client.post(f"/api/bookings/{second.pk}/confirm/").status_code, 200
        )
        self.assertEqual(
            Booking.objects.filter(status=Booking.Status.CONFIRMED).count(), 2
        )

    def test_confirm_requires_owner_membership_and_future_active_listing(self):
        booking = self.pending()
        self.auth(self.tenant)
        self.assertEqual(
            self.client.post(f"/api/bookings/{booking.pk}/confirm/").status_code, 403
        )
        self.auth(self.other_owner)
        self.assertEqual(
            self.client.post(f"/api/bookings/{booking.pk}/confirm/").status_code, 404
        )
        self.auth(self.owner)
        self.listing.is_active = False
        self.listing.save(update_fields=["is_active"])
        self.assertEqual(
            self.client.post(f"/api/bookings/{booking.pk}/confirm/").status_code, 409
        )
        self.listing.is_active = True
        self.listing.save(update_fields=["is_active"])
        booking.check_in = timezone.localdate()
        booking.save(update_fields=["check_in"])
        self.assertEqual(
            self.client.post(f"/api/bookings/{booking.pk}/confirm/").status_code, 409
        )

    def test_terminal_transitions_and_rejection_permissions(self):
        booking = self.pending()
        self.auth(self.tenant)
        self.assertEqual(
            self.client.post(f"/api/bookings/{booking.pk}/reject/").status_code, 403
        )
        self.auth(self.owner)
        self.assertEqual(
            self.client.post(f"/api/bookings/{booking.pk}/reject/").status_code, 200
        )
        self.assertEqual(
            self.client.post(f"/api/bookings/{booking.pk}/reject/").status_code, 409
        )
        self.assertEqual(
            self.client.post(f"/api/bookings/{booking.pk}/confirm/").status_code, 409
        )
        self.auth(self.tenant)
        self.assertEqual(
            self.client.post(f"/api/bookings/{booking.pk}/cancel/").status_code, 409
        )

    def test_only_tenant_may_cancel_and_repeat_is_conflict(self):
        booking = self.pending()
        self.auth(self.other_tenant)
        self.assertEqual(
            self.client.post(f"/api/bookings/{booking.pk}/cancel/").status_code, 404
        )
        self.auth(self.owner)
        self.assertEqual(
            self.client.post(f"/api/bookings/{booking.pk}/cancel/").status_code, 403
        )
        self.auth(self.tenant)
        cancelled = self.client.post(f"/api/bookings/{booking.pk}/cancel/")
        self.assertEqual(cancelled.status_code, 200, cancelled.data)
        self.assertEqual(cancelled.data["status"], Booking.Status.CANCELLED)
        self.assertIsNotNone(cancelled.data["cancelled_at"])
        self.assertEqual(
            self.client.post(f"/api/bookings/{booking.pk}/cancel/").status_code, 409
        )

    def test_confirmed_booking_can_be_cancelled_before_arrival(self):
        booking = self.pending()
        self.auth(self.owner)
        self.assertEqual(
            self.client.post(f"/api/bookings/{booking.pk}/confirm/").status_code, 200
        )
        self.auth(self.tenant)
        self.assertEqual(
            self.client.post(f"/api/bookings/{booking.pk}/cancel/").status_code, 200
        )
        booking.refresh_from_db()
        self.assertEqual(booking.status, Booking.Status.CANCELLED)

    def test_cancellation_not_allowed_on_calendar_check_in_day(self):
        booking = self.pending(
            start=timezone.localdate(), end=timezone.localdate() + timedelta(days=1)
        )
        self.auth(self.tenant)
        self.assertEqual(
            self.client.post(f"/api/bookings/{booking.pk}/cancel/").status_code, 409
        )
        self.assertEqual(
            Booking.objects.get(pk=booking.pk).status, Booking.Status.PENDING
        )

    def test_cancelled_confirmed_dates_are_released(self):
        first = self.pending()
        self.auth(self.owner)
        self.assertEqual(
            self.client.post(f"/api/bookings/{first.pk}/confirm/").status_code, 200
        )
        self.auth(self.tenant)
        self.assertEqual(
            self.client.post(f"/api/bookings/{first.pk}/cancel/").status_code, 200
        )
        second = self.pending(tenant=self.other_tenant)
        self.auth(self.owner)
        self.assertEqual(
            self.client.post(f"/api/bookings/{second.pk}/confirm/").status_code, 200
        )

    def test_lists_scopes_and_landlord_inbox_with_no_cross_user_access(self):
        active = self.pending()
        completed = self.pending(
            start=timezone.localdate() - timedelta(days=5),
            end=timezone.localdate() - timedelta(days=2),
        )
        completed.status = Booking.Status.CONFIRMED
        completed.save(update_fields=["status"])
        rejected = self.pending()
        rejected.status = Booking.Status.REJECTED
        rejected.save(update_fields=["status"])
        expired = self.pending(
            start=timezone.localdate() - timedelta(days=1),
            end=timezone.localdate() + timedelta(days=1),
        )
        expired_today = self.pending(
            start=timezone.localdate(),
            end=timezone.localdate() + timedelta(days=1),
        )
        hidden = self.pending(tenant=self.other_tenant)
        self.auth(self.tenant)
        all_rows = self.client.get("/api/bookings/")
        self.assertEqual(all_rows.status_code, 200, all_rows.data)
        self.assertEqual(all_rows.data["count"], 5)
        for scope, expected in (
            ("active", {active.pk}),
            ("completed", {completed.pk}),
            ("history", {expired.pk, expired_today.pk, rejected.pk}),
        ):
            response = self.client.get(f"/api/bookings/?scope={scope}")
            self.assertEqual(response.status_code, 200, response.data)
            self.assertEqual({row["id"] for row in response.data["results"]}, expected)
        self.assertEqual(
            self.client.get(f"/api/bookings/{hidden.pk}/").status_code, 404
        )
        self.assertEqual(
            self.client.get("/api/bookings/?scope=unknown").status_code, 400
        )
        self.assertEqual(self.client.get("/api/bookings/?status=bad").status_code, 400)
        self.assertEqual(
            self.client.get("/api/bookings/?role=landlord").status_code, 403
        )
        self.auth(self.owner)
        received = self.client.get("/api/bookings/?role=landlord")
        self.assertEqual(received.status_code, 200, received.data)
        self.assertEqual(received.data["count"], 6)
        self.assertEqual(
            self.client.get(f"/api/bookings/{hidden.pk}/").status_code, 200
        )

    def test_soft_deleted_listing_does_not_hide_historical_booking(self):
        booking = self.pending()
        self.listing.is_active = False
        self.listing.deleted_at = timezone.now()
        self.listing.save(update_fields=["is_active", "deleted_at"])
        self.auth(self.tenant)
        self.assertEqual(
            self.client.get(f"/api/bookings/{booking.pk}/").status_code, 200
        )
        self.auth(self.owner)
        self.assertEqual(
            self.client.get(f"/api/bookings/{booking.pk}/").status_code, 200
        )
        self.assertEqual(
            self.client.post(f"/api/bookings/{booking.pk}/confirm/").status_code, 409
        )

    def test_get_is_read_only_and_patch_delete_disallowed(self):
        booking = self.pending()
        self.auth(self.tenant)
        self.assertEqual(
            self.client.get(f"/api/bookings/{booking.pk}/").status_code, 200
        )
        self.assertEqual(
            self.client.patch(
                f"/api/bookings/{booking.pk}/", {"status": "CONFIRMED"}
            ).status_code,
            405,
        )
        self.assertEqual(
            self.client.delete(f"/api/bookings/{booking.pk}/").status_code, 405
        )
        booking.refresh_from_db()
        self.assertEqual(booking.status, Booking.Status.PENDING)
