from datetime import date, timedelta

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from django.db.models import Q
from django.utils import timezone
from django.utils.translation import gettext_lazy as _

MAX_STAY_NIGHTS = 365
MAX_ADVANCE_BOOKING_DAYS = 365


class BookingStatus(models.TextChoices):
    PENDING = "PENDING", _("Pending")
    CONFIRMED = "CONFIRMED", _("Confirmed")
    REJECTED = "REJECTED", _("Rejected")
    CANCELLED = "CANCELLED", _("Cancelled")


class Booking(models.Model):
    Status = BookingStatus

    listing = models.ForeignKey(
        "listings.Listing",
        on_delete=models.PROTECT,
        related_name="bookings",
        verbose_name=_("listing"),
    )
    tenant = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="bookings",
        verbose_name=_("tenant"),
    )
    check_in = models.DateField(_("check-in"))
    check_out = models.DateField(_("check-out"))
    status = models.CharField(
        _("status"),
        max_length=16,
        choices=Status.choices,
        default=Status.PENDING,
        db_collation="utf8mb4_0900_bin",
    )
    # NULL denotes an imported legacy booking with no reliable historical price.
    total_price = models.DecimalField(
        _("total price"), max_digits=13, decimal_places=2, null=True, blank=True
    )
    cancelled_at = models.DateTimeField(_("cancelled at"), null=True, blank=True)
    created_at = models.DateTimeField(_("created at"), auto_now_add=True)
    updated_at = models.DateTimeField(_("updated at"), auto_now=True)

    class Meta:
        verbose_name = _("booking")
        verbose_name_plural = _("bookings")
        ordering = ["-created_at", "-id"]
        constraints = [
            models.CheckConstraint(
                condition=Q(check_in__lt=models.F("check_out")),
                name="booking_dates_valid",
            ),
            models.CheckConstraint(
                condition=Q(status__in=tuple(BookingStatus.values)),
                name="booking_status_allowed",
            ),
            models.CheckConstraint(
                condition=Q(
                    status=BookingStatus.CANCELLED.value, cancelled_at__isnull=False
                )
                | (
                    ~Q(status=BookingStatus.CANCELLED.value)
                    & Q(cancelled_at__isnull=True)
                ),
                name="booking_cancelled_timestamp_matches",
            ),
            models.CheckConstraint(
                condition=Q(total_price__gt=0) | Q(total_price__isnull=True),
                name="booking_total_price_positive",
            ),
        ]
        indexes = [
            models.Index(
                fields=["listing", "status", "check_in", "check_out"],
                name="booking_listing_dates_idx",
            ),
            models.Index(fields=["tenant", "status"], name="booking_tenant_status_idx"),
        ]

    def clean(self):
        """Model-level safeguards; booking services must call full_clean() explicitly."""
        super().clean()
        errors = {}
        if isinstance(self.check_in, date) and isinstance(self.check_out, date):
            today = timezone.localdate()
            if self.check_out <= self.check_in:
                errors["check_out"] = "Checkout must follow check-in."
            elif (self.check_out - self.check_in).days > MAX_STAY_NIGHTS:
                errors["check_out"] = f"A stay cannot exceed {MAX_STAY_NIGHTS} nights."
            if self._state.adding and self.status == self.Status.PENDING:
                if self.check_in <= today:
                    errors["check_in"] = _("Check-in must be in the future.")
                elif self.check_in > today + timedelta(days=MAX_ADVANCE_BOOKING_DAYS):
                    errors["check_in"] = (
                        f"Check-in cannot be more than {MAX_ADVANCE_BOOKING_DAYS} days ahead."
                    )

        if (
            self._state.adding
            and self.status == self.Status.PENDING
            and self.listing_id
        ):
            from apps.listings.models import Listing

            listing = (
                Listing.objects.filter(pk=self.listing_id)
                .values("landlord_id", "is_active", "deleted_at")
                .first()
            )
            if listing:
                if self.tenant_id == listing["landlord_id"]:
                    errors["tenant"] = "A landlord cannot book their own listing."
                if not listing["is_active"] or listing["deleted_at"] is not None:
                    errors["listing"] = (
                        "This listing is not available for new bookings."
                    )
        if errors:
            raise ValidationError(errors)

    def __str__(self):
        return f"Booking #{self.pk} · listing #{self.listing_id} · {self.status}"
