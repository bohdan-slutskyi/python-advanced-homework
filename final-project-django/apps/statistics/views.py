"""Privacy-scoped history and non-identifying popularity aggregates."""

from django.db.models import Count
from django.db.models.functions import Lower
from rest_framework import generics, permissions

from apps.listings.models import Listing

from .models import SearchEvent, ViewEvent
from .retention import retention_cutoff, with_recent_view_count
from .serializers import (
    PopularListingSerializer,
    PopularSearchSerializer,
    SearchHistorySerializer,
    ViewHistorySerializer,
)


class SearchHistoryView(generics.ListAPIView):
    permission_classes = [permissions.IsAuthenticated]
    serializer_class = SearchHistorySerializer

    def get_queryset(self):
        return SearchEvent.objects.filter(
            user=self.request.user, created_at__gte=retention_cutoff()
        ).order_by("-created_at", "-id")


class ViewHistoryView(generics.ListAPIView):
    permission_classes = [permissions.IsAuthenticated]
    serializer_class = ViewHistorySerializer

    def get_queryset(self):
        return ViewEvent.objects.filter(
            viewer=self.request.user, created_at__gte=retention_cutoff()
        ).order_by("-created_at", "-id")


class PopularSearchesView(generics.ListAPIView):
    permission_classes = [permissions.AllowAny]
    serializer_class = PopularSearchSerializer

    def get_queryset(self):
        # Three distinct authenticated searchers are required for public release.
        # Anonymous events may add to the count but cannot satisfy this threshold.
        return (
            SearchEvent.objects.filter(created_at__gte=retention_cutoff())
            .annotate(query=Lower("query_text"))
            .values("query")
            .annotate(count=Count("id"), distinct_users=Count("user_id", distinct=True))
            .filter(distinct_users__gte=3)
            .order_by("-count", "query")
        )


class PopularListingsView(generics.ListAPIView):
    permission_classes = [permissions.AllowAny]
    serializer_class = PopularListingSerializer

    def get_queryset(self):
        return with_recent_view_count(
            Listing.objects.select_related("city", "district__city").filter(
                is_active=True, deleted_at__isnull=True
            )
        ).order_by("-view_count", "-id")
