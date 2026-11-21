from django.db import transaction
from django.db.models import Q
from django.utils import timezone
from drf_spectacular.utils import extend_schema, extend_schema_view
from rest_framework import permissions, viewsets
from rest_framework.response import Response

from apps.statistics.services import record_listing_view, record_search

from .filters import ListingCatalogQuerySerializer
from .models import Listing
from .permissions import IsLandlord, IsListingOwner
from .serializers import ListingSerializer


@extend_schema_view(list=extend_schema(parameters=[ListingCatalogQuerySerializer]))
class ListingViewSet(viewsets.ModelViewSet):
    serializer_class = ListingSerializer
    http_method_names = ["get", "post", "patch", "delete", "head", "options"]

    def get_permissions(self):
        if self.action in {"list", "retrieve"}:
            return [permissions.AllowAny()]
        return [permissions.IsAuthenticated(), IsLandlord(), IsListingOwner()]

    def get_queryset(self):
        qs = Listing.objects.select_related("city", "district__city").filter(
            deleted_at__isnull=True
        )
        if self.action == "list":
            params = ListingCatalogQuerySerializer(data=self.request.query_params)
            params.is_valid(raise_exception=True)
            return params.apply(qs.filter(is_active=True))
        if self.action == "retrieve":
            if self.request.user.is_authenticated:
                return qs.filter(
                    Q(is_active=True) | Q(landlord_id=self.request.user.pk)
                )
            return qs.filter(is_active=True)
        return qs

    def list(self, request, *args, **kwargs):
        response = super().list(request, *args, **kwargs)
        if request.method == "GET" and response.status_code == 200:
            record_search(request.query_params.get("search", ""), request.user)
        return response

    def retrieve(self, request, *args, **kwargs):
        listing = self.get_object()
        response = Response(self.get_serializer(listing).data)
        if request.method == "GET":
            record_listing_view(listing, request.user)
        return response

    def perform_create(self, serializer):
        serializer.save(landlord=self.request.user)

    def perform_destroy(self, instance):
        with transaction.atomic():
            listing = Listing.objects.select_for_update().get(pk=instance.pk)
            listing.deleted_at = timezone.now()
            listing.is_active = False
            listing.save(update_fields=["deleted_at", "is_active", "updated_at"])

    def perform_update(self, serializer):
        with transaction.atomic():
            serializer.instance = Listing.objects.select_for_update().get(
                pk=serializer.instance.pk, deleted_at__isnull=True
            )
            serializer.save()
