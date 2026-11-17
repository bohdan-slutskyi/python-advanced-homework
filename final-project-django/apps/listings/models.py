from decimal import Decimal

from django.conf import settings
from django.core.validators import MinValueValidator, RegexValidator
from django.db import models
from django.db.models import Q


class Listing(models.Model):
    class CountryCode(models.TextChoices):
        GERMANY = "DE", "Germany"

    class HousingType(models.TextChoices):
        APARTMENT = "APARTMENT", "Apartment"
        HOUSE = "HOUSE", "House"
        STUDIO = "STUDIO", "Studio"
        ROOM = "ROOM", "Room"

    landlord = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="listings"
    )
    title = models.CharField(max_length=200)
    description = models.TextField()
    country_code = models.CharField(
        max_length=2,
        choices=CountryCode.choices,
        default=CountryCode.GERMANY,
        db_collation="utf8mb4_0900_bin",
    )
    city = models.CharField(max_length=120)
    district = models.CharField(max_length=120, blank=True)
    postal_code = models.CharField(
        max_length=10,
        validators=[
            RegexValidator(r"^[0-9]{5}$", "A German postal code has five digits.")
        ],
    )
    street = models.CharField(max_length=200)
    house_number = models.CharField(max_length=20)
    unit_number = models.CharField(max_length=30, blank=True)
    housing_type = models.CharField(
        max_length=16, choices=HousingType.choices, db_collation="utf8mb4_0900_bin"
    )
    rooms = models.PositiveIntegerField(validators=[MinValueValidator(1)])
    price_per_night = models.DecimalField(
        max_digits=10, decimal_places=2, validators=[MinValueValidator(Decimal("0.01"))]
    )
    is_active = models.BooleanField(default=True)
    deleted_at = models.DateTimeField(null=True, blank=True, db_index=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at", "-id"]
        constraints = [
            models.CheckConstraint(
                condition=Q(country_code="DE"), name="listing_country_de"
            ),
            models.CheckConstraint(
                condition=Q(housing_type__in=("APARTMENT", "HOUSE", "STUDIO", "ROOM")),
                name="listing_housing_type",
            ),
            models.CheckConstraint(
                condition=Q(deleted_at__isnull=True) | Q(is_active=False),
                name="listing_deleted_inactive",
            ),
            models.CheckConstraint(
                condition=Q(rooms__gt=0), name="listing_rooms_gt_zero"
            ),
            models.CheckConstraint(
                condition=Q(price_per_night__gt=0), name="listing_price_gt_zero"
            ),
        ]
        indexes = [
            models.Index(
                fields=["landlord", "deleted_at"], name="listing_owner_deleted_idx"
            ),
            models.Index(fields=["city", "district"], name="listing_city_district_idx"),
        ]

    def __str__(self):
        return self.title
