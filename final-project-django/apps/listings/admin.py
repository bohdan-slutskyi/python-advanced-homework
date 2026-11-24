"""Curated geography can be managed only by Django admin staff."""

from django.contrib import admin

from .models import City, District


@admin.register(City)
class CityAdmin(admin.ModelAdmin):
    search_fields = ("name",)
    ordering = ("name",)


@admin.register(District)
class DistrictAdmin(admin.ModelAdmin):
    list_display = ("name", "city")
    list_filter = ("city",)
    search_fields = ("name", "city__name")
    list_select_related = ("city",)
    ordering = ("city__name", "name")

    def get_readonly_fields(self, request, obj=None):
        # A district's city is part of its identity. Moving it would invalidate
        # existing Listing.city / Listing.district pairs.
        return ("city",) if obj is not None else ()
