from rest_framework import serializers

from .models import City, District, Listing


class ListingSerializer(serializers.ModelSerializer):
    landlord_id = serializers.IntegerField(read_only=True)
    # Preserve the existing string-based API while the DB stores FKs.
    city = serializers.CharField(max_length=120)
    district = serializers.CharField(
        max_length=120, required=False, allow_blank=True, allow_null=True
    )

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

    def validate(self, attrs):
        city_name = attrs.pop("city", None)
        district_name = attrs.pop("district", None)
        city = self.instance.city if self.instance else None
        if city_name is not None:
            city = City.objects.filter(name__iexact=city_name.strip()).first()
            if city is None:
                raise serializers.ValidationError(
                    {"city": "Unknown city; use a registered German city."}
                )
            attrs["city"] = city
        if city is None:
            raise serializers.ValidationError({"city": "This field is required."})
        if district_name is not None:
            if not district_name.strip():
                attrs["district"] = None
            else:
                district = District.objects.filter(
                    city=city, name__iexact=district_name.strip()
                ).first()
                if district is None:
                    raise serializers.ValidationError(
                        {"district": "Unknown district for this city."}
                    )
                attrs["district"] = district
        elif self.instance is not None and self.instance.city_id != city.pk:
            # Switching city must never silently preserve a district from old city.
            if self.instance.district_id is not None:
                raise serializers.ValidationError(
                    {"district": "Specify a district of the new city or empty string."}
                )
        return attrs

    def to_representation(self, instance):
        data = super().to_representation(instance)
        # Keep the public contract as a plain district name, not District.__str__.
        data["district"] = instance.district.name if instance.district_id else ""
        return data
