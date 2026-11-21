from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from django.db.models import Q


class SearchEvent(models.Model):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL
    )
    query_text = models.CharField(max_length=255)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        constraints = [
            models.CheckConstraint(
                condition=~Q(query_text=""), name="search_query_nonempty"
            )
        ]

    def clean(self):
        super().clean()
        if isinstance(self.query_text, str):
            self.query_text = " ".join(self.query_text.split())
            if not self.query_text:
                raise ValidationError({"query_text": "A search query cannot be empty."})


class ViewEvent(models.Model):
    listing = models.ForeignKey(
        "listings.Listing", on_delete=models.PROTECT, related_name="view_events"
    )
    viewer = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL
    )
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
