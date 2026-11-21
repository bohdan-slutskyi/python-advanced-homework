"""Booking mutations with a single Listing-first lock order on MySQL."""

from decimal import Decimal

from django.core.exceptions import ValidationError as DjangoValidationError
from django.db import OperationalError, transaction
from django.utils import timezone
from rest_framework.exceptions import (
    APIException,
    NotFound,
    PermissionDenied,
    ValidationError,
)

from apps.listings.models import Listing

from .models import Booking


class BookingConflict(APIException):
    status_code = 409
    default_detail = "Booking state or dates conflict with the requested action."
    default_code = "booking_conflict"


def _validate_model(booking):
    try:
        booking.full_clean()
    except DjangoValidationError as exc:
        raise ValidationError(
            exc.message_dict if hasattr(exc, "message_dict") else exc.messages
        ) from exc


def _run_locked(operation):
    try:
        with transaction.atomic():
            return operation()
    except OperationalError as exc:
        # InnoDB deadlock / lock wait timeout: never report a successful mutation.
        if exc.args and exc.args[0] in (1205, 1213):
            raise BookingConflict("The booking is busy; retry the request.") from exc
        raise


def _listing_for_update(listing_id):
    try:
        return Listing.objects.select_for_update().get(pk=listing_id)
    except Listing.DoesNotExist as exc:
        raise NotFound("Listing not found.") from exc


def _booking_for_update(booking_id, listing_id):
    try:
        return Booking.objects.select_for_update().get(
            pk=booking_id, listing_id=listing_id
        )
    except Booking.DoesNotExist as exc:
        raise NotFound("Booking not found.") from exc


def _mutate_existing(*, booking_id, actor, operation):
    # Lookup the immutable Listing FK before taking any lock. Every mutation then
    # locks Listing first and re-reads Booking *after* obtaining that lock.
    listing_id = (
        Booking.objects.filter(pk=booking_id)
        .values_list("listing_id", flat=True)
        .first()
    )
    if listing_id is None:
        raise NotFound("Booking not found.")

    def locked():
        listing = _listing_for_update(listing_id)
        booking = _booking_for_update(booking_id, listing_id)
        return operation(listing, booking, actor)

    return _run_locked(locked)


def _confirmed_overlap(*, listing_id, check_in, check_out, exclude_id=None):
    conflicts = Booking.objects.filter(
        listing_id=listing_id,
        status=Booking.Status.CONFIRMED,
        check_in__lt=check_out,
        check_out__gt=check_in,
    )
    if exclude_id is not None:
        conflicts = conflicts.exclude(pk=exclude_id)
    return conflicts.exists()


def create_booking(*, tenant, listing_id, check_in, check_out):
    if not tenant.groups.filter(name="Tenant").exists():
        raise PermissionDenied("Tenant membership is required.")

    def locked():
        listing = _listing_for_update(listing_id)
        if listing.deleted_at is not None:
            raise NotFound("Listing not found.")
        if listing.landlord_id == tenant.pk:
            raise PermissionDenied("You cannot book your own listing.")
        if not listing.is_active:
            raise BookingConflict("Listing is not active.")
        nights = (check_out - check_in).days
        # Invalid ranges are still rejected by Booking.full_clean() below.
        total_price = (
            listing.price_per_night * Decimal(nights) if nights > 0 else Decimal("0")
        )
        booking = Booking(
            listing=listing,
            tenant=tenant,
            check_in=check_in,
            check_out=check_out,
            total_price=total_price,
        )
        _validate_model(booking)
        if _confirmed_overlap(
            listing_id=listing.pk, check_in=check_in, check_out=check_out
        ):
            raise BookingConflict("These dates overlap an existing confirmed booking.")
        booking.save()
        return booking

    return _run_locked(locked)


def confirm_booking(*, booking_id, actor):
    def confirm(listing, booking, user):
        if (
            listing.landlord_id != user.pk
            or not user.groups.filter(name="Landlord").exists()
        ):
            raise PermissionDenied("Only this listing's landlord may confirm bookings.")
        if booking.status != Booking.Status.PENDING:
            raise BookingConflict("Only pending bookings may be confirmed.")
        if listing.deleted_at is not None or not listing.is_active:
            raise BookingConflict("Listing is no longer available for confirmation.")
        if booking.check_in <= timezone.localdate():
            raise BookingConflict("Check-in must be in the future to confirm.")

        if _confirmed_overlap(
            listing_id=listing.pk,
            check_in=booking.check_in,
            check_out=booking.check_out,
            exclude_id=booking.pk,
        ):
            raise BookingConflict("These dates overlap an existing confirmed booking.")

        booking.status = Booking.Status.CONFIRMED
        _validate_model(booking)
        booking.save(update_fields=["status", "updated_at"])
        return booking

    return _mutate_existing(booking_id=booking_id, actor=actor, operation=confirm)


def reject_booking(*, booking_id, actor):
    def reject(listing, booking, user):
        if (
            listing.landlord_id != user.pk
            or not user.groups.filter(name="Landlord").exists()
        ):
            raise PermissionDenied("Only this listing's landlord may reject bookings.")
        if booking.status != Booking.Status.PENDING:
            raise BookingConflict("Only pending bookings may be rejected.")
        booking.status = Booking.Status.REJECTED
        _validate_model(booking)
        booking.save(update_fields=["status", "updated_at"])
        return booking

    return _mutate_existing(booking_id=booking_id, actor=actor, operation=reject)


def cancel_booking(*, booking_id, actor):
    def cancel(listing, booking, user):
        if (
            booking.tenant_id != user.pk
            or not user.groups.filter(name="Tenant").exists()
        ):
            raise PermissionDenied("Only the booking tenant may cancel.")
        if booking.status not in (Booking.Status.PENDING, Booking.Status.CONFIRMED):
            raise BookingConflict("This booking cannot be cancelled.")
        if timezone.localdate() >= booking.check_in:
            raise BookingConflict(
                "Cancellation closes at the start of the check-in day."
            )
        booking.status = Booking.Status.CANCELLED
        booking.cancelled_at = timezone.now()
        _validate_model(booking)
        booking.save(update_fields=["status", "cancelled_at", "updated_at"])
        return booking

    return _mutate_existing(booking_id=booking_id, actor=actor, operation=cancel)
