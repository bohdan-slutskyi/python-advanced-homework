"""Review writes enforce booking ownership and the D10 lifecycle rules."""

from django.core.exceptions import ValidationError as DjangoValidationError
from django.db import IntegrityError, OperationalError, transaction
from django.utils import timezone
from rest_framework.exceptions import (
    APIException,
    NotFound,
    PermissionDenied,
    ValidationError,
)

from apps.bookings.models import Booking

from .models import Review

REVIEW_CREATION_WINDOW_DAYS = 30


class ReviewConflict(APIException):
    status_code = 409
    default_detail = "This booking already has a review."
    default_code = "review_conflict"


def _validate_model(review):
    try:
        review.full_clean()
    except DjangoValidationError as exc:
        raise ValidationError(
            exc.message_dict if hasattr(exc, "message_dict") else exc.messages
        ) from exc


def _run_mutation(operation):
    try:
        with transaction.atomic():
            return operation()
    except IntegrityError as exc:
        if exc.args and exc.args[0] == 1062:
            raise ReviewConflict() from exc
        raise
    except OperationalError as exc:
        if exc.args and exc.args[0] in (1205, 1213):
            raise ReviewConflict("Review is busy; retry the request.") from exc
        raise


def create_review(*, actor, booking_id, rating, comment):
    if not actor.groups.filter(name="Tenant").exists():
        raise PermissionDenied("Tenant membership is required.")

    def locked():
        try:
            booking = Booking.objects.select_for_update().get(pk=booking_id)
        except Booking.DoesNotExist as exc:
            raise NotFound("Booking not found.") from exc
        if booking.tenant_id != actor.pk:
            raise NotFound("Booking not found.")
        if Review.objects.filter(booking_id=booking.pk).exists():
            raise ReviewConflict()

        review = Review(booking=booking, rating=rating, comment=comment)
        # Review.clean checks CONFIRMED and Berlin-local checkout; save does not.
        _validate_model(review)
        # The deadline applies to creation only; an existing review remains editable.
        if (
            timezone.localdate() - booking.check_out
        ).days > REVIEW_CREATION_WINDOW_DAYS:
            raise ValidationError(
                {
                    "booking": f"A review must be created within {REVIEW_CREATION_WINDOW_DAYS} days after checkout."
                }
            )
        review.save()
        return review

    return _run_mutation(locked)


def update_review(*, actor, review_id, changes):
    def locked():
        try:
            review = (
                Review.objects.select_for_update()
                .select_related("booking")
                .get(pk=review_id)
            )
        except Review.DoesNotExist as exc:
            raise NotFound("Review not found.") from exc
        if review.booking.tenant_id != actor.pk:
            raise NotFound("Review not found.")

        for field, value in changes.items():
            setattr(review, field, value)
        _validate_model(review)
        if changes:
            review.save(update_fields=[*changes, "updated_at"])
        return review

    return _run_mutation(locked)
