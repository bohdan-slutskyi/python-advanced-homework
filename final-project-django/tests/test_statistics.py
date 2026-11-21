"""D11/R21–R23: event capture, history isolation and aggregate privacy on MySQL."""

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient

from apps.listings.models import City, Listing
from apps.statistics.models import SearchEvent, ViewEvent

User = get_user_model()


class StatisticsAPITests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.users = [
            User.objects.create_user(
                email=f"stats-{i}@example.com",
                display_name=f"Searcher {i}",
                password="Test-only-password-2026!",
            )
            for i in range(4)
        ]
        cls.one = cls.make_listing("Quiet suite")
        cls.two = cls.make_listing("City loft")
        cls.hidden = cls.make_listing("Hidden unit", is_active=False)
        cls.deleted = cls.make_listing(
            "Deleted unit", is_active=False, deleted_at=timezone.now()
        )

    @classmethod
    def make_listing(cls, title, **extra):
        return Listing.objects.create(
            landlord=cls.users[0],
            title=title,
            description="An apartment for rental tests",
            city=City.objects.get(name="Hannover"),
            postal_code="30159",
            street="Teststraße",
            house_number="5",
            housing_type=Listing.HousingType.STUDIO,
            rooms=1,
            price_per_night="50.00",
            **extra,
        )

    def setUp(self):
        self.client = APIClient()

    def login_as(self, number):
        self.client.force_authenticate(self.users[number])

    def test_successful_search_records_normalized_anonymous_and_user_events(self):
        self.client.get("/api/listings/", {"search": "   Quiet   suite  "})
        self.login_as(1)
        self.client.get("/api/listings/", {"search": "LoFt"})
        events = list(SearchEvent.objects.order_by("id"))
        self.assertEqual(len(events), 2)
        self.assertEqual(
            (events[0].query_text, events[0].user_id), ("Quiet suite", None)
        )
        self.assertEqual(
            (events[1].query_text, events[1].user_id),
            ("LoFt", self.users[1].pk),
        )
        self.assertFalse(hasattr(events[0], "ip_address"))
        self.assertFalse(hasattr(events[0], "user_agent"))

    def test_ignored_searches_and_failed_requests_do_not_create_events(self):
        for params in (
            {},
            {"search": ""},
            {"search": "   "},
        ):
            self.assertEqual(self.client.get("/api/listings/", params).status_code, 200)
        for params in (
            {"search": "x" * 201},
            {"search": "valid", "min_price": "invalid"},
            {"search": "valid", "ordering": "unknown"},
        ):
            self.assertEqual(self.client.get("/api/listings/", params).status_code, 400)
        self.assertEqual(
            self.client.get(
                "/api/listings/", {"search": "valid", "page": 999}
            ).status_code,
            404,
        )
        self.client.head("/api/listings/", {"search": "valid"})
        self.assertEqual(SearchEvent.objects.count(), 0)

    def test_retrieve_records_real_views_but_not_head_or_unavailable(self):
        self.assertEqual(
            self.client.get(f"/api/listings/{self.one.pk}/").status_code, 200
        )
        self.login_as(1)
        self.assertEqual(
            self.client.get(f"/api/listings/{self.one.pk}/").status_code, 200
        )
        self.assertEqual(
            self.client.head(f"/api/listings/{self.one.pk}/").status_code, 200
        )
        self.assertEqual(
            self.client.get(f"/api/listings/{self.hidden.pk}/").status_code, 404
        )
        self.assertEqual(
            self.client.get(f"/api/listings/{self.deleted.pk}/").status_code, 404
        )
        # Owners can preview inactive listings, without inflating public popularity.
        self.login_as(0)
        self.assertEqual(
            self.client.get(f"/api/listings/{self.hidden.pk}/").status_code, 200
        )
        events = list(ViewEvent.objects.order_by("pk"))
        self.assertEqual(len(events), 2)
        self.assertEqual([event.listing_id for event in events], [self.one.pk] * 2)
        self.assertEqual(
            [event.viewer_id for event in events], [None, self.users[1].pk]
        )

    def test_user_histories_are_authenticated_isolated_and_paginated(self):
        self.login_as(1)
        for term in ("first", "second"):
            self.client.get("/api/listings/", {"search": term})
        self.client.get(f"/api/listings/{self.one.pk}/")
        self.login_as(2)
        self.client.get("/api/listings/", {"search": "private"})
        self.client.get(f"/api/listings/{self.two.pk}/")
        self.client.force_authenticate(user=None)
        for endpoint in ("search-history", "view-history"):
            response = self.client.get(f"/api/statistics/{endpoint}/")
            self.assertEqual(response.status_code, 401)

        self.login_as(1)
        search = self.client.get("/api/statistics/search-history/")
        view = self.client.get("/api/statistics/view-history/")
        self.assertEqual(search.status_code, 200)
        self.assertEqual(view.status_code, 200)
        self.assertEqual(search.data["count"], 2)
        self.assertEqual(
            {item["query_text"] for item in search.data["results"]},
            {"first", "second"},
        )
        self.assertEqual(view.data["count"], 1)
        self.assertEqual(view.data["results"][0]["listing_id"], self.one.pk)
        self.assertEqual(
            set(view.data["results"][0]), {"id", "listing_id", "created_at"}
        )
        self.assertNotIn("user_id", search.data["results"][0])
        self.assertNotIn("viewer_id", view.data["results"][0])
        # Listing history retains the ID after soft delete, but no private metadata.
        Listing.objects.filter(pk=self.one.pk).update(
            deleted_at=timezone.now(), is_active=False
        )
        preserved = self.client.get("/api/statistics/view-history/")
        self.assertEqual(preserved.data["results"][0]["listing_id"], self.one.pk)

        self.login_as(2)
        own = self.client.get("/api/statistics/search-history/")
        self.assertEqual([x["query_text"] for x in own.data["results"]], ["private"])
        self.assertEqual(
            self.client.get("/api/statistics/view-history/").data["count"], 1
        )
        self.assertEqual(SearchEvent.objects.count(), 3)

    def test_histories_use_stable_pagination(self):
        self.login_as(1)
        SearchEvent.objects.bulk_create(
            [
                SearchEvent(user=self.users[1], query_text=f"query {i}")
                for i in range(24)
            ]
        )
        first = self.client.get("/api/statistics/search-history/")
        next_page = self.client.get("/api/statistics/search-history/?page=2")
        self.assertEqual((first.data["count"], len(first.data["results"])), (24, 20))
        self.assertEqual(len(next_page.data["results"]), 4)
        ids = [row["id"] for row in first.data["results"] + next_page.data["results"]]
        self.assertEqual(len(set(ids)), 24)

    def test_popular_searches_hides_rare_queries_and_needs_three_distinct_users(self):
        for _ in range(4):
            SearchEvent.objects.create(user=self.users[1], query_text="secret")
        for user in self.users[:2]:
            SearchEvent.objects.create(user=user, query_text="Quiet Stay")
        response = self.client.get("/api/statistics/popular-searches/")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["results"], [])

        SearchEvent.objects.create(user=self.users[2], query_text="quiet stay")
        SearchEvent.objects.create(user=None, query_text="QUIET STAY")
        released = self.client.get("/api/statistics/popular-searches/")
        self.assertEqual(released.status_code, 200)
        self.assertEqual(
            released.data["results"], [{"query": "quiet stay", "count": 4}]
        )
        self.assertNotIn("distinct_users", released.data["results"][0])

    def test_popular_listings_and_catalog_ordering_hide_nonpublic_listings(self):
        for listing, count in (
            (self.one, 3),
            (self.two, 1),
            (self.hidden, 10),
            (self.deleted, 10),
        ):
            ViewEvent.objects.bulk_create(
                [ViewEvent(listing=listing, viewer=self.users[1]) for _ in range(count)]
            )
        result = self.client.get("/api/statistics/popular-listings/")
        self.assertEqual(result.status_code, 200)
        self.assertEqual(
            result.data["results"],
            [
                {"id": self.one.pk, "title": "Quiet suite", "view_count": 3},
                {"id": self.two.pk, "title": "City loft", "view_count": 1},
            ],
        )
        self.assertEqual(
            [
                obj["id"]
                for obj in self.client.get(
                    "/api/listings/", {"ordering": "popular"}
                ).data["results"]
            ],
            [self.one.pk, self.two.pk],
        )
        self.assertEqual(
            [
                obj["id"]
                for obj in self.client.get(
                    "/api/listings/", {"ordering": "popular", "search": "city"}
                ).data["results"]
            ],
            [self.two.pk],
        )

    def test_popular_ordering_ties_are_deterministic_and_invalid_rejected(self):
        self.assertEqual(
            [
                obj["id"]
                for obj in self.client.get(
                    "/api/listings/", {"ordering": "popular"}
                ).data["results"]
            ],
            [self.two.pk, self.one.pk],
        )
        self.assertEqual(
            self.client.get("/api/listings/", {"ordering": "-popular"}).status_code, 400
        )
        self.assertEqual(
            self.client.get("/api/statistics/popular-searches/").status_code, 200
        )
        self.assertEqual(SearchEvent.objects.count(), 0)

    def test_openapi_documents_statistics_auth_and_popular_ordering(self):
        schema = self.client.get("/api/schema/")
        self.assertEqual(schema.status_code, 200)
        paths = schema.data["paths"]
        for name in (
            "search-history",
            "view-history",
            "popular-listings",
            "popular-searches",
        ):
            self.assertIn(f"/api/statistics/{name}/", paths)
            self.assertIn("get", paths[f"/api/statistics/{name}/"])
        params = paths["/api/listings/"]["get"]["parameters"]
        ordering = next(param for param in params if param["name"] == "ordering")
        enum = ordering["schema"]
        if "$ref" in enum:
            enum = schema.data["components"]["schemas"][enum["$ref"].split("/")[-1]]
        self.assertIn("popular", enum["enum"])
