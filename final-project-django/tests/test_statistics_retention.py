"""Regression coverage for analytics expiry and optional event writes."""

from datetime import timedelta
from io import StringIO
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.db import DatabaseError, IntegrityError
from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient

from apps.listings.models import City, Listing
from apps.statistics.models import SearchEvent, ViewEvent
from apps.statistics.retention import RETENTION_DAYS


class StatisticsRetentionTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.users = [
            get_user_model().objects.create_user(
                email=f"retention-{i}@example.invalid", display_name=f"User {i}"
            )
            for i in range(3)
        ]
        cls.recent = cls.make_listing("Recent listing")
        cls.stale = cls.make_listing("Stale listing")
        cls.zero = cls.make_listing("No views")

    @classmethod
    def make_listing(cls, title):
        return Listing.objects.create(
            landlord=cls.users[0],
            title=title,
            description="Retention boundary",
            city=City.objects.get(name="Berlin"),
            postal_code="10115",
            street="Test street",
            house_number="1",
            housing_type=Listing.HousingType.STUDIO,
            rooms=1,
            price_per_night="50.00",
        )

    def setUp(self):
        self.client = APIClient()
        self.now = timezone.now().replace(microsecond=0)
        self.cutoff = self.now - timedelta(days=RETENTION_DAYS)
        self.fresh = self.cutoff + timedelta(seconds=1)
        self.expired = self.cutoff - timedelta(seconds=1)
        clock = patch("apps.statistics.retention.timezone.now", return_value=self.now)
        clock.start()
        self.addCleanup(clock.stop)

    def search(self, user, term, when):
        event = SearchEvent.objects.create(user=user, query_text=term)
        SearchEvent.objects.filter(pk=event.pk).update(created_at=when)
        return event.pk

    def view(self, user, listing, when):
        event = ViewEvent.objects.create(viewer=user, listing=listing)
        ViewEvent.objects.filter(pk=event.pk).update(created_at=when)
        return event.pk

    def results(self, path, **params):
        response = self.client.get(path, params)
        self.assertEqual(response.status_code, 200, response.data)
        return response.data["results"]

    def test_private_histories_use_inclusive_cutoff_without_purge(self):
        self.client.force_authenticate(self.users[0])
        search_ids = [
            self.search(self.users[0], "test phrase", when)
            for when in (self.fresh, self.cutoff, self.expired)
        ]
        view_ids = [
            self.view(self.users[0], self.recent, when)
            for when in (self.fresh, self.cutoff, self.expired)
        ]
        self.search(self.users[1], "other user", self.fresh)
        self.view(self.users[1], self.recent, self.fresh)
        self.assertEqual(
            [row["id"] for row in self.results("/api/statistics/search-history/")],
            search_ids[:2],
        )
        self.assertEqual(
            [row["id"] for row in self.results("/api/statistics/view-history/")],
            view_ids[:2],
        )
        self.assertEqual(SearchEvent.objects.count(), 4)
        self.assertEqual(ViewEvent.objects.count(), 4)

    def test_popular_search_privacy_threshold_and_counts_use_same_window(self):
        for user, when in zip(
            self.users, (self.fresh, self.cutoff, self.expired), strict=True
        ):
            self.search(user, "Private phrase", when)
        self.search(None, "private phrase", self.fresh)
        self.assertEqual(self.results("/api/statistics/popular-searches/"), [])
        self.search(self.users[2], "PRIVATE PHRASE", self.cutoff)
        self.search(None, "private phrase", self.expired)
        self.assertEqual(
            self.results("/api/statistics/popular-searches/"),
            [{"query": "private phrase", "count": 4}],
        )
        self.assertEqual(SearchEvent.objects.count(), 6)

    def test_both_popularity_rankings_ignore_expired_views_and_keep_zero_views(self):
        self.view(self.users[0], self.recent, self.fresh)
        self.view(self.users[0], self.recent, self.cutoff)
        self.view(self.users[0], self.recent, self.expired)
        for _ in range(5):
            self.view(self.users[1], self.stale, self.expired)
        ranking = self.results("/api/statistics/popular-listings/")
        self.assertEqual(
            [(row["id"], row["view_count"]) for row in ranking],
            [(self.recent.pk, 2), (self.zero.pk, 0), (self.stale.pk, 0)],
        )
        self.assertEqual(
            [row["id"] for row in self.results("/api/listings/", ordering="popular")],
            [self.recent.pk, self.zero.pk, self.stale.pk],
        )
        self.assertEqual(ViewEvent.objects.count(), 8)

    def test_manual_purge_and_read_cutoffs_agree_at_boundary(self):
        for when in (self.fresh, self.cutoff, self.expired):
            self.search(self.users[0], "boundary", when)
            self.view(self.users[0], self.recent, when)
        call_command("purge_statistics", stdout=StringIO())
        self.assertEqual(SearchEvent.objects.count(), 3)
        self.assertEqual(ViewEvent.objects.count(), 3)
        call_command("purge_statistics", apply=True, stdout=StringIO())
        self.assertEqual(
            set(SearchEvent.objects.values_list("created_at", flat=True)),
            {self.fresh, self.cutoff},
        )
        self.assertEqual(
            set(ViewEvent.objects.values_list("created_at", flat=True)),
            {self.fresh, self.cutoff},
        )

    def test_failed_event_writes_do_not_break_get_or_leak_query_text(self):
        self.client.force_authenticate(self.users[0])
        secret_term = "Recent"
        for model, path, params in (
            (SearchEvent, "/api/listings/", {"search": secret_term}),
            (ViewEvent, f"/api/listings/{self.recent.pk}/", {}),
        ):
            with (
                self.subTest(model=model.__name__),
                patch.object(
                    model.objects,
                    "create",
                    side_effect=DatabaseError("private SQL detail"),
                ),
                self.assertLogs("apps.statistics.services", level="WARNING") as logs,
            ):
                result = self.client.get(path, params)
                self.assertEqual(result.status_code, 200, result.data)
                if model is SearchEvent:
                    self.assertEqual(
                        [row["id"] for row in result.data["results"]], [self.recent.pk]
                    )
                else:
                    self.assertEqual(result.data["id"], self.recent.pk)
                self.assertEqual(
                    logs.output,
                    [
                        f"WARNING:apps.statistics.services:Analytics event write failed: {model.__name__}"
                    ],
                )
        self.assertEqual(SearchEvent.objects.count(), 0)
        self.assertEqual(ViewEvent.objects.count(), 0)

    def test_real_failed_insert_rolls_back_savepoint_not_outer_transaction(self):
        create = SearchEvent.objects.create

        def bad_insert(**kwargs):
            kwargs["query_text"] = ""
            return create(**kwargs)

        with (
            patch.object(SearchEvent.objects, "create", side_effect=bad_insert),
            self.assertLogs("apps.statistics.services", level="WARNING"),
        ):
            response = self.client.get("/api/listings/", {"search": "Recent"})
        self.assertEqual(response.status_code, 200, response.data)
        self.assertEqual(SearchEvent.objects.count(), 0)
        self.assertEqual(Listing.objects.count(), 3)
        self.assertEqual(
            self.client.get("/api/listings/", {"search": "Recent"}).status_code,
            200,
        )
        self.assertEqual(SearchEvent.objects.count(), 1)

    def test_catalog_read_error_is_not_swallowed_as_analytics_error(self):
        with (
            patch(
                "apps.listings.views.ListingViewSet.get_queryset",
                side_effect=IntegrityError("read failed"),
            ),
            self.assertRaises(IntegrityError),
        ):
            self.client.get("/api/listings/", {"search": "Recent"})
        self.assertEqual(SearchEvent.objects.count(), 0)
