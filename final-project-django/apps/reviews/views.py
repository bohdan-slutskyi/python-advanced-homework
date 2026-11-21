"""Review write endpoints and listing-scoped public/historical review reads."""

from django.db.models import Avg, Count, Q
from django.shortcuts import get_object_or_404
from drf_spectacular.utils import extend_schema
from rest_framework import generics, mixins, permissions, status, viewsets
from rest_framework.pagination import PageNumberPagination
from rest_framework.response import Response

from apps.listings.models import Listing

from .models import Review
from .serializers import (
    ReviewCreateSerializer,
    ReviewPublicSerializer,
    ReviewReadSerializer,
    ReviewUpdateSerializer,
)
from .services import create_review, update_review


def visible_listings(user):
    public = Q(is_active=True, deleted_at__isnull=True)
    if user.is_authenticated:
        public |= Q(landlord_id=user.pk) | Q(bookings__tenant_id=user.pk)
    return Listing.objects.filter(public).distinct()


class ReviewViewSet(
    mixins.RetrieveModelMixin,
    viewsets.GenericViewSet,
):
    serializer_class = ReviewReadSerializer
    http_method_names = ["get", "post", "patch", "head", "options"]

    def get_serializer_class(self):
        if self.action == "retrieve":
            return ReviewPublicSerializer
        return ReviewReadSerializer

    def get_permissions(self):
        if self.action == "retrieve":
            return [permissions.AllowAny()]
        return [permissions.IsAuthenticated()]

    def get_queryset(self):
        qs = Review.objects.select_related("booking")
        if self.action == "retrieve":
            return qs.filter(
                booking__listing_id__in=visible_listings(self.request.user).values("pk")
            )
        if self.action == "partial_update":
            return qs.filter(booking__tenant_id=self.request.user.pk)
        return qs.none()

    @extend_schema(
        request=ReviewCreateSerializer, responses={201: ReviewReadSerializer}
    )
    def create(self, request, *args, **kwargs):
        serializer = ReviewCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        review = create_review(actor=request.user, **serializer.validated_data)
        return Response(
            ReviewReadSerializer(review).data, status=status.HTTP_201_CREATED
        )

    @extend_schema(request=ReviewUpdateSerializer, responses=ReviewReadSerializer)
    def partial_update(self, request, *args, **kwargs):
        review = self.get_object()
        serializer = ReviewUpdateSerializer(data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        updated = update_review(
            actor=request.user, review_id=review.pk, changes=serializer.validated_data
        )
        return Response(ReviewReadSerializer(updated).data)


class ListingReviewsPagination(PageNumberPagination):
    """Document aggregate fields returned with each paginated review list."""

    def get_paginated_response_schema(self, schema):
        result = super().get_paginated_response_schema(schema)
        result["properties"].update(
            average_rating={"type": "number", "nullable": True},
            review_count={"type": "integer", "minimum": 0},
        )
        result["required"] = ["count", "results", "average_rating", "review_count"]
        return result


class ListingReviewsView(generics.ListAPIView):
    permission_classes = [permissions.AllowAny]
    serializer_class = ReviewPublicSerializer
    pagination_class = ListingReviewsPagination

    def get_listing(self):
        if not hasattr(self, "_listing"):
            self._listing = get_object_or_404(
                visible_listings(self.request.user), pk=self.kwargs["pk"]
            )
        return self._listing

    def get_queryset(self):
        return Review.objects.filter(
            booking__listing_id=self.get_listing().pk
        ).select_related("booking")

    @extend_schema(responses=ReviewPublicSerializer(many=True))
    def list(self, request, *args, **kwargs):
        response = super().list(request, *args, **kwargs)
        summary = self.get_queryset().aggregate(
            average_rating=Avg("rating"), review_count=Count("id")
        )
        response.data["average_rating"] = summary["average_rating"]
        response.data["review_count"] = summary["review_count"]
        return response
