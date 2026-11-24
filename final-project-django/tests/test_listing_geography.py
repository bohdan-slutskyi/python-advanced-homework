"""Regression coverage for district update semantics and admin protection."""

from unittest.mock import patch

from django.contrib.admin.sites import AdminSite
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.db import OperationalError
from django.test import RequestFactory, TestCase
from rest_framework.test import APIClient

from apps.listings.admin import DistrictAdmin
from apps.listings.models import City, District, Listing
from apps.listings.views import ListingViewSet


class ListingGeographyTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.owner = get_user_model().objects.create_user(
            email="geography-owner@example.invalid", display_name="Owner"
        )
        cls.owner.groups.add(Group.objects.get(name="Landlord"))
        cls.berlin = City.objects.get(name="Berlin")
        cls.hannover = City.objects.get(name="Hannover")
        cls.mitte = District.objects.get(city=cls.berlin, name="Mitte")
        cls.listing = Listing.objects.create(
            landlord=cls.owner,
            title="District regression",
            description="Location test",
            city=cls.berlin,
            district=cls.mitte,
            postal_code="10115",
            street="Test street",
            house_number="1",
            housing_type=Listing.HousingType.STUDIO,
            rooms=1,
            price_per_night="50.00",
        )

    def setUp(self):
        self.client = APIClient()
        self.client.force_authenticate(self.owner)
        self.url = f"/api/listings/{self.listing.pk}/"

    def test_api_serializes_district_name_without_calling_its_str(self):
        with patch.object(
            District,
            "__str__",
            side_effect=AssertionError("Must not build admin label"),
        ):
            response = self.client.get(self.url)
            self.assertEqual(response.status_code, 200, response.data)
            self.assertEqual(response.data["district"], "Mitte")
            response = self.client.get("/api/listings/")
            self.assertEqual(response.status_code, 200, response.data)
            self.assertEqual(response.data["results"][0]["district"], "Mitte")

    def test_lock_errors_return_conflict_and_rollback_listing_mutation(self):
        initial = Listing.objects.filter(pk=self.listing.pk).values().get()
        for method, hook in (
            ("patch", "perform_update"),
            ("delete", "perform_destroy"),
        ):
            original = getattr(ListingViewSet, hook)
            for code in (1205, 1213):

                def mutate_then_fail(view, obj):
                    original(view, obj)
                    raise OperationalError(code, "Synthetic MySQL lock error")

                with (
                    self.subTest(method=method, code=code),
                    patch.object(
                        ListingViewSet,
                        hook,
                        autospec=True,
                        side_effect=mutate_then_fail,
                    ),
                ):
                    response = getattr(self.client, method)(
                        self.url,
                        {"title": "Must roll back"} if method == "patch" else {},
                        format="json",
                    )
                    self.assertEqual(response.status_code, 409, response.data)
                    self.assertEqual(
                        str(response.data["detail"]),
                        "The listing is busy; retry the request.",
                    )
                    self.assertEqual(
                        Listing.objects.filter(pk=self.listing.pk).values().get(),
                        initial,
                    )

    def test_unrelated_operational_errors_are_not_mapped_to_conflicts(self):
        initial = Listing.objects.filter(pk=self.listing.pk).values().get()
        for method, hook in (
            ("patch", "perform_update"),
            ("delete", "perform_destroy"),
        ):
            original = getattr(ListingViewSet, hook)

            def mutate_then_fail(view, obj):
                original(view, obj)
                raise OperationalError(1054, "Synthetic unrelated SQL error")

            with (
                self.subTest(method=method),
                patch.object(
                    ListingViewSet, hook, autospec=True, side_effect=mutate_then_fail
                ),
                self.assertRaises(OperationalError) as caught,
            ):
                getattr(self.client, method)(
                    self.url,
                    {"title": "Must roll back"} if method == "patch" else {},
                    format="json",
                )
            self.assertEqual(caught.exception.args[0], 1054)
            self.assertEqual(
                Listing.objects.filter(pk=self.listing.pk).values().get(), initial
            )

    def test_omitted_district_preserves_current_value(self):
        response = self.client.patch(self.url, {"title": "Changed"}, format="json")
        self.assertEqual(response.status_code, 200, response.data)
        self.listing.refresh_from_db()
        self.assertEqual(self.listing.district_id, self.mitte.pk)
        self.assertEqual(response.data["district"], "Mitte")

    def test_null_or_blank_district_explicitly_clears_value(self):
        for value in (None, ""):
            with self.subTest(value=value):
                Listing.objects.filter(pk=self.listing.pk).update(district=self.mitte)
                response = self.client.patch(
                    self.url, {"district": value}, format="json"
                )
                self.assertEqual(response.status_code, 200, response.data)
                self.listing.refresh_from_db()
                self.assertIsNone(self.listing.district_id)
                self.assertEqual(response.data["district"], "")

    def test_city_change_requires_valid_district_or_explicit_clear(self):
        for payload in (
            {"city": "Hannover"},
            {"city": "Hannover", "district": "Kreuzberg"},
        ):
            response = self.client.patch(self.url, payload, format="json")
            self.assertEqual(response.status_code, 400, response.data)
            self.listing.refresh_from_db()
            self.assertEqual(self.listing.city_id, self.berlin.pk)
            self.assertEqual(self.listing.district_id, self.mitte.pk)
        response = self.client.patch(
            self.url, {"city": "Hannover", "district": None}, format="json"
        )
        self.assertEqual(response.status_code, 200, response.data)
        self.listing.refresh_from_db()
        self.assertEqual(self.listing.city_id, self.hannover.pk)
        self.assertIsNone(self.listing.district_id)
        response = self.client.patch(self.url, {"district": "Mitte"}, format="json")
        self.assertEqual(response.status_code, 200, response.data)
        self.listing.refresh_from_db()
        self.assertEqual(self.listing.district.city_id, self.hannover.pk)

    def test_create_accepts_omitted_null_or_blank_district(self):
        payload = {
            "title": "New listing",
            "description": "Location test",
            "city": "Berlin",
            "postal_code": "10115",
            "street": "Test street",
            "house_number": "1",
            "housing_type": "STUDIO",
            "rooms": 1,
            "price_per_night": "50.00",
        }
        for extra in ({}, {"district": None}, {"district": ""}):
            with self.subTest(extra=extra):
                response = self.client.post(
                    "/api/listings/", {**payload, **extra}, format="json"
                )
                self.assertEqual(response.status_code, 201, response.data)
                self.assertIsNone(
                    Listing.objects.get(pk=response.data["id"]).district_id
                )
                self.assertEqual(response.data["district"], "")

    def test_existing_district_city_is_readonly_in_admin(self):
        request = RequestFactory().get("/admin/listings/district/")
        request.user = self.owner
        request.user.is_staff = True
        request.user.is_superuser = True
        district_admin = DistrictAdmin(District, AdminSite())
        form_class = district_admin.get_form(request, obj=self.mitte)
        self.assertNotIn("city", form_class.base_fields)
        self.assertIn("city", district_admin.get_form(request).base_fields)
        form = form_class(
            data={"name": "Mitte", "city": self.hannover.pk}, instance=self.mitte
        )
        self.assertTrue(form.is_valid(), form.errors)
        form.save()
        self.mitte.refresh_from_db()
        self.assertEqual(self.mitte.city_id, self.berlin.pk)
