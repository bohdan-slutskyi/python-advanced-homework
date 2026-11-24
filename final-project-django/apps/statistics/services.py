"""Record only successful, meaningful public listing interactions."""

import logging

from django.db import DatabaseError, transaction

from .models import SearchEvent, ViewEvent

logger = logging.getLogger(__name__)


def _record_event(model, **fields):
    # Catch outside the atomic block so a failed INSERT rolls back its savepoint.
    # Do not include query text, user IDs or SQL/exception details in the log.
    try:
        with transaction.atomic():
            model.objects.create(**fields)
    except DatabaseError:
        logger.warning("Analytics event write failed: %s", model.__name__)


def actor_or_none(user):
    return user if user.is_authenticated else None


def record_search(query, user):
    normalized = " ".join(query.split())
    if normalized:
        _record_event(SearchEvent, user=actor_or_none(user), query_text=normalized)


def record_listing_view(listing, user):
    if listing.is_active and listing.deleted_at is None:
        _record_event(ViewEvent, listing=listing, viewer=actor_or_none(user))
