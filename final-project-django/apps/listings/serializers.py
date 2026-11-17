from rest_framework import serializers

from .models import Listing


class ListingSerializer(serializers.ModelSerializer):
    landlord_id = serializers.IntegerField(read_only=True)

    class Meta:
        model = Listing
        fields = [
            "id",
            "landlord_id",
            "title",
            "description",
            "country_code",
            "city",
            "district",
            "postal_code",
            "street",
            "house_number",
            "unit_number",
            "housing_type",
            "rooms",
            "price_per_night",
            "is_active",
            "created_at",
            "updated_at",
        ]
        read_only_fields = [
            "id",
            "landlord_id",
            "country_code",
            "created_at",
            "updated_at",
        ]
