"""Read-only booking resources with explicit transactional state-change actions."""

from django.db.models import Q
from django.utils import timezone
from drf_spectacular.utils import OpenApiParameter, extend_schema
from rest_framework import mixins, permissions, status, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import PermissionDenied
from rest_framework.response import Response

from apps.listings.permissions import IsLandlord

from .models import Booking
from .serializers import (
    BookingCreateSerializer,
    BookingQuerySerializer,
    BookingReadSerializer,
)
from .services import cancel_booking, confirm_booking, create_booking, reject_booking


class IsTenant(permissions.BasePermission):
    message = "Tenant membership is required."

    def has_permission(self, request, view):
        return bool(
            request.user.is_authenticated
            and request.user.groups.filter(name="Tenant").exists()
        )


class BookingViewSet(
    mixins.ListModelMixin,
    mixins.RetrieveModelMixin,
    viewsets.GenericViewSet,
):
    serializer_class = BookingReadSerializer
    http_method_names = ["get", "post", "head", "options"]

    def get_permissions(self):
        required = [permissions.IsAuthenticated()]
        if self.action in {"create", "cancel"}:
            required.append(IsTenant())
        if self.action in {"confirm", "reject"}:
            required.append(IsLandlord())
        return required

    def get_queryset(self):
        user = self.request.user
        if not user.is_authenticated:
            return Booking.objects.none()
        qs = Booking.objects.select_related("listing", "tenant")
        if self.action != "list":
            return qs.filter(Q(tenant_id=user.pk) | Q(listing__landlord_id=user.pk))

        params = BookingQuerySerializer(data=self.request.query_params)
        params.is_valid(raise_exception=True)
        filters = params.validated_data
        if filters["role"] == "landlord":
            if not user.groups.filter(name="Landlord").exists():
                raise PermissionDenied("Landlord membership is required.")
            qs = qs.filter(listing__landlord_id=user.pk)
        else:
            qs = qs.filter(tenant_id=user.pk)

        today = timezone.localdate()
        if filters.get("scope") == "active":
            qs = qs.filter(
                Q(status=Booking.Status.PENDING, check_in__gt=today)
                | Q(status=Booking.Status.CONFIRMED, check_out__gt=today)
            )
        elif filters.get("scope") == "completed":
            qs = qs.filter(status=Booking.Status.CONFIRMED, check_out__lte=today)
        elif filters.get("scope") == "history":
            qs = qs.filter(
                Q(status__in=(Booking.Status.CANCELLED, Booking.Status.REJECTED))
                | Q(status=Booking.Status.PENDING, check_in__lte=today)
            )
        if "status" in filters:
            qs = qs.filter(status=filters["status"])
        return qs

    @extend_schema(
        parameters=[
            OpenApiParameter("role", str, description="tenant (default) or landlord"),
            OpenApiParameter("scope", str, description="active, completed or history"),
            OpenApiParameter("status", str, description="Booking status choice"),
        ]
    )
    def list(self, request, *args, **kwargs):
        return super().list(request, *args, **kwargs)

    @extend_schema(
        request=BookingCreateSerializer, responses={201: BookingReadSerializer}
    )
    def create(self, request, *args, **kwargs):
        serializer = BookingCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        booking = create_booking(tenant=request.user, **serializer.validated_data)
        return Response(
            BookingReadSerializer(booking).data, status=status.HTTP_201_CREATED
        )

    @extend_schema(request=None, responses=BookingReadSerializer)
    @action(detail=True, methods=["post"])
    def confirm(self, request, pk=None):
        booking = confirm_booking(booking_id=self.get_object().pk, actor=request.user)
        return Response(BookingReadSerializer(booking).data)

    @extend_schema(request=None, responses=BookingReadSerializer)
    @action(detail=True, methods=["post"])
    def reject(self, request, pk=None):
        booking = reject_booking(booking_id=self.get_object().pk, actor=request.user)
        return Response(BookingReadSerializer(booking).data)

    @extend_schema(request=None, responses=BookingReadSerializer)
    @action(detail=True, methods=["post"])
    def cancel(self, request, pk=None):
        booking = cancel_booking(booking_id=self.get_object().pk, actor=request.user)
        return Response(BookingReadSerializer(booking).data)
