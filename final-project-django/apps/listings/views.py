from django.db import transaction
from django.db.models import Q
from django.utils import timezone
from rest_framework import permissions, viewsets

from .models import Listing
from .permissions import IsLandlord, IsListingOwner
from .serializers import ListingSerializer


class ListingViewSet(viewsets.ModelViewSet):
    serializer_class = ListingSerializer
    http_method_names = ["get", "post", "patch", "delete", "head", "options"]

    def get_permissions(self):
        if self.action in {"list", "retrieve"}:
            return [permissions.AllowAny()]
        return [permissions.IsAuthenticated(), IsLandlord(), IsListingOwner()]

    def get_queryset(self):
        qs = Listing.objects.filter(deleted_at__isnull=True)
        if self.action == "list":
            return qs.filter(is_active=True)
        if self.action == "retrieve":
            if self.request.user.is_authenticated:
                return qs.filter(
                    Q(is_active=True) | Q(landlord_id=self.request.user.pk)
                )
            return qs.filter(is_active=True)
        return qs

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
