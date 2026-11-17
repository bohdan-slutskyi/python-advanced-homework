from datetime import date, timedelta

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from django.db.models import Q
from django.utils import timezone


class Booking(models.Model):
    class Status(models.TextChoices):
        PENDING = "PENDING", "Pending"
        CONFIRMED = "CONFIRMED", "Confirmed"
        REJECTED = "REJECTED", "Rejected"
        CANCELLED = "CANCELLED", "Cancelled"

    listing = models.ForeignKey(
        "listings.Listing", on_delete=models.PROTECT, related_name="bookings"
    )
    tenant = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="bookings"
    )
    check_in = models.DateField()
    check_out = models.DateField()
    status = models.CharField(
        max_length=16,
        choices=Status.choices,
        default=Status.PENDING,
        db_collation="utf8mb4_0900_bin",
    )
    cancelled_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at", "-id"]
        constraints = [
            models.CheckConstraint(
                condition=Q(check_in__lt=models.F("check_out")),
                name="booking_dates_valid",
            ),
            models.CheckConstraint(
                condition=Q(
                    status__in=("PENDING", "CONFIRMED", "REJECTED", "CANCELLED")
                ),
                name="booking_status_allowed",
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
            elif (self.check_out - self.check_in).days > 365:
                errors["check_out"] = "A stay cannot exceed 365 nights."
            if self._state.adding and self.status == self.Status.PENDING:
                if self.check_in < today:
                    errors["check_in"] = "Check-in cannot be in the past."
                elif self.check_in > today + timedelta(days=365):
                    errors["check_in"] = "Check-in cannot be more than 365 days ahead."

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
