"""Public catalog search, filters, ordering and schema on MySQL."""

from datetime import timedelta

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient

from apps.listings.models import City, District, Listing

User = get_user_model()
BASE = {
    "description": "Comfortable stay",
    "city": "Hannover",
    "district": "Mitte",
    "postal_code": "30159",
    "street": "Teststraße",
    "house_number": "1",
    "housing_type": Listing.HousingType.STUDIO,
    "rooms": 1,
    "price_per_night": "80.00",
}


class ListingCatalogAPITests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.owner = User.objects.create_user(
            email="catalog-owner@example.com",
            display_name="Catalog Owner",
            password="Only-For-Tests-2026!",
        )
        cls.studio = cls.make_listing(
            "Modern Studio", description="Near the museum", days_ago=4
        )
        cls.house = cls.make_listing(
            "Family House",
            description="River views",
            district="List",
            housing_type=Listing.HousingType.HOUSE,
            rooms=3,
            price_per_night="150.00",
            days_ago=3,
        )
        cls.flat = cls.make_listing(
            "Quiet Flat",
            description="Museum district retreat",
            city="Berlin",
            district="Kreuzberg",
            housing_type=Listing.HousingType.APARTMENT,
            rooms=2,
            price_per_night="100.00",
            days_ago=2,
        )
        cls.sunny = cls.make_listing(
            "Sunny Flat",
            city="Berlin",
            district="Mitte",
            housing_type=Listing.HousingType.APARTMENT,
            days_ago=1,
        )
        cls.hidden = cls.make_listing(
            "Museum hidden", is_active=False, price_per_night="40.00"
        )
        cls.deleted = cls.make_listing(
            "Museum deleted",
            deleted_at=timezone.now(),
            is_active=False,
            price_per_night="30.00",
        )

    @classmethod
    def make_listing(cls, title, days_ago=0, **changes):
        attrs = {**BASE, **changes}
        city = City.objects.get(name=attrs.pop("city"))
        district_name = attrs.pop("district", "")
        district = (
            District.objects.get(city=city, name=district_name)
            if district_name
            else None
        )
        listing = Listing.objects.create(
            landlord=cls.owner, title=title, city=city, district=district, **attrs
        )
        if days_ago:
            Listing.objects.filter(pk=listing.pk).update(
                created_at=timezone.now() - timedelta(days=days_ago)
            )
        return listing

    def setUp(self):
        self.client = APIClient()

    def get_ids(self, **params):
        response = self.client.get("/api/listings/", params)
        self.assertEqual(response.status_code, 200, response.data)
        return [item["id"] for item in response.data["results"]]

    def test_anonymous_catalog_hides_inactive_and_soft_deleted(self):
        expected = [self.sunny.pk, self.flat.pk, self.house.pk, self.studio.pk]
        self.assertEqual(self.get_ids(), expected)
        self.client.force_authenticate(self.owner)
        self.assertEqual(self.get_ids(), expected)
        self.assertEqual(
            self.client.get(f"/api/listings/{self.hidden.pk}/").status_code, 200
        )

    def test_search_title_description_case_insensitive_and_empty(self):
        self.assertEqual(self.get_ids(search="mUsEuM"), [self.flat.pk, self.studio.pk])
        self.assertEqual(self.get_ids(search="MODERN"), [self.studio.pk])
        self.assertEqual(self.get_ids(search="no such apartment"), [])
        self.assertEqual(len(self.get_ids(search="   ")), 4)
        self.assertEqual(self.get_ids(search="%"), [])

    def test_price_inclusive_boundaries_and_decimal_filters(self):
        self.assertEqual(
            self.get_ids(min_price="80.00", max_price="100.00"),
            [self.sunny.pk, self.flat.pk, self.studio.pk],
        )
        self.assertEqual(self.get_ids(min_price="100", max_price="100"), [self.flat.pk])
        self.assertEqual(self.get_ids(min_price="0", max_price="0"), [])
        self.assertEqual(self.get_ids(max_price="79.99"), [])

    def test_rejects_invalid_price_parameters(self):
        for params in (
            {"min_price": "-0.01"},
            {"max_price": "-1"},
            {"min_price": "abc"},
            {"max_price": "80.001"},
            {"min_price": "120", "max_price": "80"},
            {"max_price": "999999999.99"},
            {"min_price": ""},
        ):
            with self.subTest(params=params):
                response = self.client.get("/api/listings/", params)
                self.assertEqual(response.status_code, 400, response.data)

    def test_city_district_case_insensitive_and_combined(self):
        self.assertEqual(self.get_ids(city="berLIN"), [self.sunny.pk, self.flat.pk])
        self.assertEqual(
            self.get_ids(district="mITTE"), [self.sunny.pk, self.studio.pk]
        )
        self.assertEqual(
            self.get_ids(city="Hannover", district="list"), [self.house.pk]
        )
        self.assertEqual(self.get_ids(city="Bonn"), [])
        self.assertEqual(len(self.get_ids(city="", district="")), 4)

    def test_room_range_inclusive_and_invalid_inputs(self):
        self.assertEqual(
            self.get_ids(rooms_min=1, rooms_max=2),
            [self.sunny.pk, self.flat.pk, self.studio.pk],
        )
        self.assertEqual(self.get_ids(rooms_min=3, rooms_max=3), [self.house.pk])
        for params in (
            {"rooms_min": 0},
            {"rooms_max": -1},
            {"rooms_min": "1.5"},
            {"rooms_max": "x"},
            {"rooms_min": 3, "rooms_max": 1},
            {"rooms_min": ""},
        ):
            with self.subTest(params=params):
                response = self.client.get("/api/listings/", params)
                self.assertEqual(response.status_code, 400, response.data)

    def test_housing_type_allowed_choices_and_strict_case(self):
        self.assertEqual(
            self.get_ids(housing_type="APARTMENT"), [self.sunny.pk, self.flat.pk]
        )
        self.assertEqual(self.get_ids(housing_type="ROOM"), [])
        for value in ("apartment", "INVALID", "", "APARTMENT' OR 1=1"):
            with self.subTest(value=value):
                response = self.client.get("/api/listings/", {"housing_type": value})
                self.assertEqual(response.status_code, 400, response.data)

    def test_four_orderings_are_stable_with_price_ties(self):
        self.assertEqual(
            self.get_ids(ordering="price"),
            [self.studio.pk, self.sunny.pk, self.flat.pk, self.house.pk],
        )
        self.assertEqual(
            self.get_ids(ordering="-price"),
            [self.house.pk, self.flat.pk, self.sunny.pk, self.studio.pk],
        )
        self.assertEqual(
            self.get_ids(ordering="created_at"),
            [self.studio.pk, self.house.pk, self.flat.pk, self.sunny.pk],
        )
        self.assertEqual(
            self.get_ids(ordering="-created_at"),
            [self.sunny.pk, self.flat.pk, self.house.pk, self.studio.pk],
        )
        self.assertEqual(self.get_ids(ordering="-created_at"), self.get_ids())

    def test_ordering_rejects_unknown_or_multiple_fields(self):
        for value in ("id", "landlord_id", "random()", "price,-price", ""):
            with self.subTest(value=value):
                response = self.client.get("/api/listings/", {"ordering": value})
                self.assertEqual(response.status_code, 400, response.data)

    def test_composed_filters_and_ordering(self):
        self.assertEqual(
            self.get_ids(
                search="flat",
                city="Berlin",
                district="Mitte",
                min_price="80",
                max_price="90",
                rooms_min=1,
                rooms_max=2,
                housing_type="APARTMENT",
                ordering="-price",
            ),
            [self.sunny.pk],
        )
        self.assertEqual(self.get_ids(city="Berlin", housing_type="HOUSE"), [])

    def test_catalog_pagination_has_no_duplicates_across_price_ties(self):
        created = [
            self.make_listing(f"Extra listing {number}", days_ago=8)
            for number in range(24)
        ]
        response1 = self.client.get("/api/listings/", {"ordering": "price"})
        response2 = self.client.get("/api/listings/", {"ordering": "price", "page": 2})
        self.assertEqual(response1.status_code, 200, response1.data)
        self.assertEqual(response2.status_code, 200, response2.data)
        self.assertEqual(response1.data["count"], 28)
        ids1 = [item["id"] for item in response1.data["results"]]
        ids2 = [item["id"] for item in response2.data["results"]]
        self.assertEqual(len(ids1), 20)
        self.assertEqual(len(ids2), 8)
        self.assertEqual(len(set(ids1 + ids2)), 28)
        self.assertEqual(
            ids1 + ids2,
            [
                self.studio.pk,
                self.sunny.pk,
                *[obj.pk for obj in created],
                self.flat.pk,
                self.house.pk,
            ],
        )

    def test_openapi_exposes_catalog_parameters_and_allowed_orderings(self):
        response = self.client.get("/api/schema/")
        self.assertEqual(response.status_code, 200)
        params = response.data["paths"]["/api/listings/"]["get"]["parameters"]
        names = {param["name"] for param in params}
        self.assertTrue(
            {
                "search",
                "min_price",
                "max_price",
                "city",
                "district",
                "rooms_min",
                "rooms_max",
                "housing_type",
                "ordering",
            }.issubset(names)
        )
        ordering = next(param for param in params if param["name"] == "ordering")
        schema = ordering["schema"]
        if "$ref" in schema:
            schema = response.data["components"]["schemas"][
                schema["$ref"].split("/")[-1]
            ]
        self.assertEqual(
            set(schema["enum"]),
            {"price", "-price", "created_at", "-created_at", "popular"},
        )
