from rest_framework.permissions import BasePermission, SAFE_METHODS


class IsOwnerOrReadOnly(BasePermission):
    """Только владелец может изменять или удалять задачу и подзадачу."""

    message = "Вы не являетесь владельцем этого объекта."

    def has_object_permission(self, request, view, obj):
        if request.method in SAFE_METHODS:
            return True
        return obj.owner_id is not None and obj.owner_id == request.user.pk
