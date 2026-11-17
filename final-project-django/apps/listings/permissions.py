from rest_framework.permissions import BasePermission


class IsLandlord(BasePermission):
    message = "Landlord membership is required."

    def has_permission(self, request, view):
        return bool(
            request.user.is_authenticated
            and request.user.groups.filter(name="Landlord").exists()
        )


class IsListingOwner(BasePermission):
    message = "Only the listing owner may change it."

    def has_object_permission(self, request, view, obj):
        return obj.landlord_id == request.user.pk
