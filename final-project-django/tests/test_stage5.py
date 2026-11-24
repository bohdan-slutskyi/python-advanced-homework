"""Stage 5: seed reproducibility, event retention, query shape and API boundaries."""

from datetime import timedelta
from io import StringIO

from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.core.management.base import CommandError
from django.db import connection
from django.test import TestCase
from django.test.utils import CaptureQueriesContext
from django.utils import timezone
from rest_framework.test import APIClient

from apps.bookings.models import Booking
from apps.listings.models import Listing
from apps.reviews.models import Review
from apps.statistics.models import SearchEvent, ViewEvent
from apps.statistics.retention import with_recent_view_count


class StageFiveTest(TestCase):
    def seed(self, **kwargs):
        options = dict(
            seed=51271,
            landlords=2,
            tenants=5,
            listings=10,
            bookings=20,
            reviews=4,
            events=20,
        )
        options.update(kwargs)
        out = StringIO()
        call_command("seed_demo", stdout=out, **options)
        return out.getvalue()

    def test_seed_repeatable_and_existing_user_untouched(self):
        User = get_user_model()
        original = User.objects.create_user(
            email="existing@example.invalid", display_name="Not a demo"
        )
        first = self.seed()
        self.assertIn("users=7 new", first)
        snapshot = (
            User.objects.count(),
            Listing.objects.count(),
            Booking.objects.count(),
            Review.objects.count(),
            SearchEvent.objects.count(),
            ViewEvent.objects.count(),
        )
        second = self.seed()
        self.assertIn("users=0 new", second)
        self.assertEqual(
            snapshot,
            (
                User.objects.count(),
                Listing.objects.count(),
                Booking.objects.count(),
                Review.objects.count(),
                SearchEvent.objects.count(),
                ViewEvent.objects.count(),
            ),
        )
        original.refresh_from_db()
        self.assertEqual(original.display_name, "Not a demo")
        self.assertEqual(
            Booking.objects.filter(status=Booking.Status.CONFIRMED).count(), 20
        )
        self.assertEqual(Review.objects.count(), 4)
        self.assertTrue(
            all(
                item.booking.check_out <= timezone.localdate()
                for item in Review.objects.select_related("booking")
            )
        )
        for landlord in User.objects.filter(email__contains="-landlord-"):
            self.assertTrue(landlord.groups.filter(name="Landlord").exists())

    def test_seed_repeatable_after_normal_duplicate_searches_and_views(self):
        self.seed()
        user = get_user_model().objects.get(
            email="demo-51271-tenant-00000@example.invalid"
        )
        listing = Listing.objects.get(title="[DEMO 51271] Listing 00000")
        client = APIClient()
        client.force_authenticate(user)
        for _ in range(2):
            self.assertEqual(
                client.get(
                    "/api/listings/", {"search": "demo-51271 city-0"}
                ).status_code,
                200,
            )
            self.assertEqual(
                client.get(f"/api/listings/{listing.pk}/").status_code, 200
            )
        self.assertEqual(
            SearchEvent.objects.filter(
                user=user, query_text="demo-51271 city-0"
            ).count(),
            3,
        )
        self.assertEqual(
            ViewEvent.objects.filter(viewer=user, listing=listing).count(), 3
        )
        models = (get_user_model(), Listing, Booking, Review, SearchEvent, ViewEvent)
        before = [list(model.objects.order_by("pk").values()) for model in models]
        second = self.seed()
        for name in (
            "users",
            "listings",
            "bookings",
            "reviews",
            "search_events",
            "view_events",
        ):
            self.assertIn(f"{name}=0 new", second)
        self.assertEqual(
            [list(model.objects.order_by("pk").values()) for model in models], before
        )

    def test_invalid_seed_arguments_write_nothing(self):
        with self.assertRaises(CommandError):
            self.seed(reviews=11)
        with self.assertRaises(CommandError):
            self.seed(events=51)
        self.assertEqual(Listing.objects.count(), 0)

    def test_purge_dry_run_then_apply_preserves_rental_history(self):
        self.seed()
        old = timezone.now() - timedelta(days=91)
        old_search = SearchEvent.objects.first()
        old_view = ViewEvent.objects.first()
        SearchEvent.objects.filter(pk=old_search.pk).update(created_at=old)
        ViewEvent.objects.filter(pk=old_view.pk).update(created_at=old)
        result = StringIO()
        call_command("purge_statistics", stdout=result)
        self.assertIn("would delete", result.getvalue())
        self.assertEqual(SearchEvent.objects.count(), 20)
        self.assertEqual(ViewEvent.objects.count(), 20)
        call_command("purge_statistics", apply=True, batch_size=1, stdout=StringIO())
        self.assertEqual(SearchEvent.objects.count(), 19)
        self.assertEqual(ViewEvent.objects.count(), 19)
        self.assertEqual(Booking.objects.count(), 20)
        self.assertEqual(Review.objects.count(), 4)
        self.assertEqual(Listing.objects.count(), 10)
        with self.assertRaises(CommandError):
            call_command("purge_statistics", days=0, stdout=StringIO())

    def test_private_history_and_no_n_plus_one_on_popularity(self):
        self.seed(listings=30, bookings=60, reviews=10, events=120)
        client = APIClient()
        self.assertEqual(client.get("/api/statistics/view-history/").status_code, 401)
        users = list(
            get_user_model()
            .objects.filter(email__startswith="demo-51271-tenant-")
            .order_by("id")
        )
        client.force_authenticate(user=users[0])
        own_views = client.get("/api/statistics/view-history/").json()
        self.assertGreater(own_views["count"], 0)
        self.assertTrue(all("viewer_id" not in v for v in own_views["results"]))
        client.force_authenticate(user=users[1])
        second = client.get("/api/statistics/view-history/").json()
        own_ids = {v["id"] for v in own_views["results"]}
        self.assertFalse(own_ids & {v["id"] for v in second["results"]})
        client.force_authenticate(user=None)
        with CaptureQueriesContext(connection) as queries:
            response = client.get("/api/listings/?ordering=popular&page=1")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["count"], 30)
        self.assertLessEqual(len(queries), 4)
        with CaptureQueriesContext(connection) as queries:
            response = client.get("/api/statistics/popular-listings/")
        self.assertEqual(response.status_code, 200)
        self.assertLessEqual(len(queries), 4)

    def test_filters_and_bad_pagination_under_seed(self):
        self.seed(listings=30, bookings=60, reviews=10, events=120)
        client = APIClient()
        response = client.get(
            "/api/listings/?min_price=40&max_price=240&rooms_min=1&rooms_max=5"
            "&ordering=-price&page=1"
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["count"], 30)
        self.assertLessEqual(len(response.json()["results"]), 20)
        self.assertEqual(client.get("/api/listings/?rooms_min=0").status_code, 400)
        self.assertEqual(client.get("/api/listings/?ordering=bogus").status_code, 400)
        self.assertEqual(client.get("/api/listings/?page=999").status_code, 404)
        self.assertEqual(
            client.get("/api/statistics/popular-searches/").status_code, 200
        )

    def test_mysql_explain_shape_for_popular_listings(self):
        self.seed()
        qs = with_recent_view_count(
            Listing.objects.filter(is_active=True, deleted_at__isnull=True)
        ).order_by("-view_count", "-id")
        plan = qs.explain()
        self.assertTrue(plan.strip())
        self.assertIn("listings_listing", plan)
