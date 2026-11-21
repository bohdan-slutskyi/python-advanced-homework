"""Record only successful, meaningful public listing interactions."""

from .models import SearchEvent, ViewEvent


def actor_or_none(user):
    return user if user.is_authenticated else None


def record_search(query, user):
    normalized = " ".join(query.split())
    if normalized:
        SearchEvent.objects.create(user=actor_or_none(user), query_text=normalized)


def record_listing_view(listing, user):
    if listing.is_active and listing.deleted_at is None:
        ViewEvent.objects.create(listing=listing, viewer=actor_or_none(user))
