"""Explicit read and write contracts for reviews."""

from rest_framework import serializers

from .models import Review


class ReviewCreateSerializer(serializers.Serializer):
    booking_id = serializers.IntegerField(min_value=1)
    rating = serializers.IntegerField(min_value=1, max_value=5)
    comment = serializers.CharField(trim_whitespace=True, allow_blank=False)


class ReviewUpdateSerializer(serializers.Serializer):
    rating = serializers.IntegerField(min_value=1, max_value=5, required=False)
    comment = serializers.CharField(
        trim_whitespace=True, allow_blank=False, required=False
    )


class ReviewPublicSerializer(serializers.ModelSerializer):
    """Public reviews do not expose the guest or their booking identifier."""

    class Meta:
        model = Review
        fields = ("id", "rating", "comment", "created_at", "updated_at")
        read_only_fields = fields


class ReviewReadSerializer(serializers.ModelSerializer):
    booking_id = serializers.IntegerField(read_only=True)
    listing_id = serializers.IntegerField(source="booking.listing_id", read_only=True)
    tenant_id = serializers.IntegerField(source="booking.tenant_id", read_only=True)

    class Meta:
        model = Review
        fields = (
            "id",
            "booking_id",
            "listing_id",
            "tenant_id",
            "rating",
            "comment",
            "created_at",
            "updated_at",
        )
        read_only_fields = fields
