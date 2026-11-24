"""Deterministic InnoDB races between API requests using separate connections."""

from concurrent.futures import ThreadPoolExecutor
from threading import Event
from unittest import skipUnless

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.db import connection, connections, transaction
from django.test import TransactionTestCase
from rest_framework.test import APIClient

from apps.listings.models import City, District, Listing


@skipUnless(connection.vendor == "mysql", "Concurrency acceptance needs real MySQL")
class ListingConcurrencyTests(TransactionTestCase):
    def setUp(self):
        self.owner = get_user_model().objects.create_user(
            email="listing-race-owner@example.invalid", display_name="Owner"
        )
        self.owner.groups.add(Group.objects.get_or_create(name="Landlord")[0])
        berlin = City.objects.get_or_create(name="Berlin")[0]
        self.hannover = City.objects.get_or_create(name="Hannover")[0]
        mitte = District.objects.get_or_create(city=berlin, name="Mitte")[0]
        District.objects.get_or_create(city=berlin, name="Kreuzberg")
        self.hannover_mitte = District.objects.get_or_create(
            city=self.hannover, name="Mitte"
        )[0]
        self.listing = Listing.objects.create(
            landlord=self.owner,
            title="Concurrent location test",
            description="InnoDB row lock",
            city=berlin,
            district=mitte,
            postal_code="10115",
            street="Test street",
            house_number="1",
            housing_type=Listing.HousingType.STUDIO,
            rooms=1,
            price_per_night="50.00",
        )
        self.url = f"/api/listings/{self.listing.pk}/"

    def client_for_owner(self):
        client = APIClient()
        client.force_authenticate(self.owner)
        return client

    def race(self, first_action, second_payload):
        lock_attempted = Event()
        primary_thread = connection.connection.thread_id()

        def second_patch():
            def observe_lock(execute, sql, params, many, context):
                if "FOR UPDATE" in sql.upper() and "listings_listing" in sql:
                    lock_attempted.set()
                return execute(sql, params, many, context)

            try:
                connection.ensure_connection()
                thread_id = connection.connection.thread_id()
                with connection.execute_wrapper(observe_lock):
                    response = self.client_for_owner().patch(
                        self.url, second_payload, format="json"
                    )
                return thread_id, response.status_code
            finally:
                connections.close_all()

        with ThreadPoolExecutor(max_workers=1) as pool:
            with transaction.atomic():
                Listing.objects.select_for_update().get(pk=self.listing.pk)
                future = pool.submit(second_patch)
                self.assertTrue(
                    lock_attempted.wait(timeout=10), "No competing row lock"
                )
                first_action(self.client_for_owner())
            secondary_thread, status = future.result(timeout=20)
        self.assertNotEqual(primary_thread, secondary_thread)
        return status

    def test_patch_validates_against_committed_city_after_waiting_for_lock(self):
        def change_city(client):
            response = client.patch(
                self.url, {"city": "Hannover", "district": "Mitte"}, format="json"
            )
            self.assertEqual(response.status_code, 200, response.data)

        self.assertEqual(self.race(change_city, {"district": "Kreuzberg"}), 400)
        self.listing.refresh_from_db()
        self.assertEqual(self.listing.city_id, self.hannover.pk)
        self.assertEqual(self.listing.district_id, self.hannover_mitte.pk)

    def test_patch_waiting_on_deleted_listing_returns_404(self):
        def delete(client):
            self.assertEqual(client.delete(self.url).status_code, 204)

        original_title = self.listing.title
        self.assertEqual(self.race(delete, {"title": "Too late"}), 404)
        self.listing.refresh_from_db()
        self.assertIsNotNone(self.listing.deleted_at)
        self.assertFalse(self.listing.is_active)
        self.assertEqual(self.listing.title, original_title)
