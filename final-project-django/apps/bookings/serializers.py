"""Explicit write fields prevent client-controlled status, tenant or timestamps."""

from rest_framework import serializers

from .models import Booking


class BookingCreateSerializer(serializers.Serializer):
    listing_id = serializers.IntegerField(min_value=1)
    check_in = serializers.DateField()
    check_out = serializers.DateField()


class BookingReadSerializer(serializers.ModelSerializer):
    listing_id = serializers.IntegerField(read_only=True)
    tenant_id = serializers.IntegerField(read_only=True)

    class Meta:
        model = Booking
        fields = (
            "id",
            "listing_id",
            "tenant_id",
            "check_in",
            "check_out",
            "status",
            "total_price",
            "cancelled_at",
            "created_at",
            "updated_at",
        )
        read_only_fields = fields


class BookingQuerySerializer(serializers.Serializer):
    role = serializers.ChoiceField(choices=("tenant", "landlord"), default="tenant")
    scope = serializers.ChoiceField(
        choices=("active", "completed", "history"), required=False
    )
    status = serializers.ChoiceField(choices=Booking.Status.values, required=False)
