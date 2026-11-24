"""Validated public catalog parameters and ORM filtering."""

from decimal import Decimal

from django.db.models import Q
from rest_framework import serializers

from apps.statistics.retention import with_recent_view_count

from .models import Listing


class ListingCatalogQuerySerializer(serializers.Serializer):
    search = serializers.CharField(required=False, allow_blank=True, max_length=200)
    min_price = serializers.DecimalField(
        required=False, max_digits=10, decimal_places=2, min_value=Decimal("0")
    )
    max_price = serializers.DecimalField(
        required=False, max_digits=10, decimal_places=2, min_value=Decimal("0")
    )
    city = serializers.CharField(required=False, allow_blank=True, max_length=120)
    district = serializers.CharField(required=False, allow_blank=True, max_length=120)
    rooms_min = serializers.IntegerField(required=False, min_value=1)
    rooms_max = serializers.IntegerField(required=False, min_value=1)
    housing_type = serializers.ChoiceField(
        required=False, choices=Listing.HousingType.choices
    )
    ordering = serializers.ChoiceField(
        required=False,
        choices=("price", "-price", "created_at", "-created_at", "popular"),
        help_text="Price/date in both directions, or most viewed first.",
    )

    def to_internal_value(self, data):
        blank_fields = (
            "min_price",
            "max_price",
            "rooms_min",
            "rooms_max",
            "housing_type",
            "ordering",
        )
        errors = {
            field: ["This parameter cannot be empty."]
            for field in blank_fields
            if field in data and data.get(field) == ""
        }
        if errors:
            raise serializers.ValidationError(errors)
        return super().to_internal_value(data)

    def validate(self, attrs):
        if (
            "min_price" in attrs
            and "max_price" in attrs
            and attrs["min_price"] > attrs["max_price"]
        ):
            raise serializers.ValidationError(
                {"max_price": "Must be greater than or equal to min_price."}
            )
        if (
            "rooms_min" in attrs
            and "rooms_max" in attrs
            and attrs["rooms_min"] > attrs["rooms_max"]
        ):
            raise serializers.ValidationError(
                {"rooms_max": "Must be greater than or equal to rooms_min."}
            )
        return attrs

    def apply(self, queryset):
        """Filter a visibility-restricted queryset; never expose hidden listings."""
        params = self.validated_data
        if term := params.get("search"):
            queryset = queryset.filter(
                Q(title__icontains=term) | Q(description__icontains=term)
            )
        for key, lookup in (
            ("min_price", "price_per_night__gte"),
            ("max_price", "price_per_night__lte"),
            ("rooms_min", "rooms__gte"),
            ("rooms_max", "rooms__lte"),
        ):
            if key in params:
                queryset = queryset.filter(**{lookup: params[key]})
        for key in ("city", "district"):
            if value := params.get(key):
                queryset = queryset.filter(**{f"{key}__name__iexact": value})
        if "housing_type" in params:
            queryset = queryset.filter(housing_type=params["housing_type"])
        if params.get("ordering") == "popular":
            return with_recent_view_count(queryset).order_by("-view_count", "-id")
        ordering = {
            "price": ("price_per_night", "id"),
            "-price": ("-price_per_night", "-id"),
            "created_at": ("created_at", "id"),
            "-created_at": ("-created_at", "-id"),
        }.get(params.get("ordering"), ("-created_at", "-id"))
        return queryset.order_by(*ordering)
