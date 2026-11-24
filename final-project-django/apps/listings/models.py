from decimal import Decimal

from django.conf import settings
from django.core.validators import MaxValueValidator, MinValueValidator, RegexValidator
from django.db import models
from django.db.models import Q
from django.utils.translation import gettext_lazy as _

MAX_ROOMS = 100


class City(models.Model):
    """Controlled municipality catalogue; populated by migrations/admin."""

    name = models.CharField(_("name"), max_length=120, unique=True)

    class Meta:
        verbose_name = _("city")
        verbose_name_plural = _("cities")
        ordering = ["name"]

    def __str__(self):
        return self.name


class District(models.Model):
    """A district name is unique only inside its municipality."""

    city = models.ForeignKey(
        City, on_delete=models.PROTECT, related_name="districts", verbose_name=_("city")
    )
    name = models.CharField(_("name"), max_length=120)

    class Meta:
        verbose_name = _("district")
        verbose_name_plural = _("districts")
        ordering = ["city_id", "name"]
        constraints = [
            models.UniqueConstraint(
                fields=["city", "name"], name="district_city_name_uq"
            )
        ]

    def __str__(self):
        return f"{self.name}, {self.city.name}"


class CountryCode(models.TextChoices):
    GERMANY = "DE", _("Germany")


class HousingType(models.TextChoices):
    APARTMENT = "APARTMENT", _("Apartment")
    HOUSE = "HOUSE", _("House")
    STUDIO = "STUDIO", _("Studio")
    ROOM = "ROOM", _("Room")


class Listing(models.Model):
    CountryCode = CountryCode
    HousingType = HousingType

    landlord = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="listings",
        verbose_name=_("landlord"),
    )
    title = models.CharField(_("title"), max_length=200)
    description = models.TextField(_("description"))
    country_code = models.CharField(
        _("country code"),
        max_length=2,
        choices=CountryCode.choices,
        default=CountryCode.GERMANY,
        db_collation="utf8mb4_0900_bin",
    )
    city = models.ForeignKey(
        City, on_delete=models.PROTECT, related_name="listings", verbose_name=_("city")
    )
    district = models.ForeignKey(
        District,
        on_delete=models.PROTECT,
        related_name="listings",
        null=True,
        blank=True,
        verbose_name=_("district"),
    )
    # Exact pre-normalization values retained only for migration audit/rollback.
    legacy_city = models.CharField(
        _("legacy city"), max_length=120, blank=True, default="", editable=False
    )
    legacy_district = models.CharField(
        _("legacy district"), max_length=120, blank=True, default="", editable=False
    )
    postal_code = models.CharField(
        _("postal code"),
        max_length=5,
        validators=[
            RegexValidator(r"\A[0-9]{5}\Z", "A German postal code has five digits.")
        ],
    )
    street = models.CharField(_("street"), max_length=200)
    house_number = models.CharField(_("house number"), max_length=20)
    unit_number = models.CharField(_("unit number"), max_length=30, blank=True)
    housing_type = models.CharField(
        _("housing type"),
        max_length=16,
        choices=HousingType.choices,
        db_collation="utf8mb4_0900_bin",
    )
    rooms = models.PositiveIntegerField(
        _("rooms"), validators=[MinValueValidator(1), MaxValueValidator(MAX_ROOMS)]
    )
    price_per_night = models.DecimalField(
        _("price per night"),
        max_digits=10,
        decimal_places=2,
        validators=[MinValueValidator(Decimal("0.01"))],
    )
    is_active = models.BooleanField(_("active"), default=True)
    deleted_at = models.DateTimeField(
        _("deleted at"), null=True, blank=True, db_index=False
    )
    created_at = models.DateTimeField(_("created at"), auto_now_add=True)
    updated_at = models.DateTimeField(_("updated at"), auto_now=True)

    class Meta:
        verbose_name = _("listing")
        verbose_name_plural = _("listings")
        ordering = ["-created_at", "-id"]
        constraints = [
            models.CheckConstraint(
                condition=Q(country_code=CountryCode.GERMANY.value),
                name="listing_country_de",
            ),
            models.CheckConstraint(
                condition=Q(housing_type__in=tuple(HousingType.values)),
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
                condition=Q(rooms__lte=MAX_ROOMS), name="listing_rooms_lte_max"
            ),
            models.CheckConstraint(
                condition=Q(price_per_night__gt=0), name="listing_price_gt_zero"
            ),
            models.CheckConstraint(
                condition=Q(postal_code__regex=r"^[0-9]{5}$")
                & ~Q(postal_code__regex=r"[^0-9]"),
                name="listing_postal_code_ascii_digits",
            ),
        ]
        indexes = [
            models.Index(
                fields=["landlord", "deleted_at"], name="listing_owner_deleted_idx"
            ),
            models.Index(fields=["city", "district"], name="listing_city_district_idx"),
        ]

    def clean(self):
        from django.core.exceptions import ValidationError

        super().clean()
        if self.district_id and self.city_id:
            if not District.objects.filter(
                pk=self.district_id, city_id=self.city_id
            ).exists():
                raise ValidationError({"district": "District must belong to city."})

    def __str__(self):
        return self.title
