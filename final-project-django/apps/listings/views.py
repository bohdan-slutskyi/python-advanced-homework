from django.db import OperationalError, transaction
from django.db.models import Q
from django.utils import timezone
from drf_spectacular.utils import extend_schema, extend_schema_view
from rest_framework import permissions, viewsets
from rest_framework.exceptions import APIException
from rest_framework.response import Response

from apps.statistics.services import record_listing_view, record_search

from .filters import ListingCatalogQuerySerializer
from .models import Listing
from .permissions import IsLandlord, IsListingOwner
from .serializers import ListingSerializer


class ListingConflict(APIException):
    status_code = 409
    default_detail = "The listing is busy; retry the request."
    default_code = "listing_conflict"


def _run_locked(operation):
    try:
        with transaction.atomic():
            return operation()
    except OperationalError as exc:
        if exc.args and exc.args[0] in (1205, 1213):
            raise ListingConflict() from exc
        raise


@extend_schema_view(list=extend_schema(parameters=[ListingCatalogQuerySerializer]))
class ListingViewSet(viewsets.ModelViewSet):
    serializer_class = ListingSerializer
    http_method_names = ["get", "post", "patch", "delete", "head", "options"]

    def get_permissions(self):
        if self.action in {"list", "retrieve"}:
            return [permissions.AllowAny()]
        return [permissions.IsAuthenticated(), IsLandlord(), IsListingOwner()]

    def get_queryset(self):
        if self.action in {"update", "partial_update", "destroy"}:
            # update/destroy own the transaction. Lock only the Listing row,
            # before object permissions and serializer validation run.
            return Listing.objects.select_for_update().filter(deleted_at__isnull=True)
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

    def update(self, request, *args, **kwargs):
        operation = super().update
        return _run_locked(lambda: operation(request, *args, **kwargs))

    def destroy(self, request, *args, **kwargs):
        operation = super().destroy
        return _run_locked(lambda: operation(request, *args, **kwargs))

    def perform_destroy(self, instance):
        instance.deleted_at = timezone.now()
        instance.is_active = False
        instance.save(update_fields=["deleted_at", "is_active", "updated_at"])
