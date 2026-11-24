from django.core.exceptions import ValidationError
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models
from django.db.models import Q
from django.utils import timezone
from django.utils.translation import gettext_lazy as _


class Review(models.Model):
    booking = models.OneToOneField(
        "bookings.Booking",
        on_delete=models.PROTECT,
        related_name="review",
        verbose_name=_("booking"),
    )
    rating = models.PositiveSmallIntegerField(
        _("rating"), validators=[MinValueValidator(1), MaxValueValidator(5)]
    )
    comment = models.TextField(_("comment"))
    created_at = models.DateTimeField(_("created at"), auto_now_add=True)
    updated_at = models.DateTimeField(_("updated at"), auto_now=True)

    class Meta:
        verbose_name = _("review")
        verbose_name_plural = _("reviews")
        ordering = ["-created_at", "-id"]
        constraints = [
            models.CheckConstraint(
                condition=Q(rating__gte=1, rating__lte=5), name="review_rating_1_to_5"
            ),
        ]

    def clean(self):
        """Eligibility is rechecked by the reviews service before saving."""
        super().clean()
        if isinstance(self.comment, str) and not self.comment.strip():
            raise ValidationError({"comment": _("A review comment cannot be blank.")})
        if self.booking_id:
            from apps.bookings.models import Booking

            booking = (
                Booking.objects.filter(pk=self.booking_id)
                .only("status", "check_out")
                .first()
            )
            if booking is not None:
                if booking.status != Booking.Status.CONFIRMED:
                    raise ValidationError(
                        {"booking": "Only confirmed stays can be reviewed."}
                    )
                if booking.check_out > timezone.localdate():
                    raise ValidationError(
                        {"booking": "A review is allowed only after checkout."}
                    )

    def __str__(self):
        return f"Review #{self.pk} · booking #{self.booking_id} · {self.rating}/5"
