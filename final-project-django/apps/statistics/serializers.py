from rest_framework import serializers

from apps.listings.models import Listing

from .models import SearchEvent, ViewEvent


class SearchHistorySerializer(serializers.ModelSerializer):
    class Meta:
        model = SearchEvent
        fields = ("id", "query_text", "created_at")


class ViewHistorySerializer(serializers.ModelSerializer):
    class Meta:
        model = ViewEvent
        fields = ("id", "listing_id", "created_at")


class PopularSearchSerializer(serializers.Serializer):
    query = serializers.CharField()
    count = serializers.IntegerField()


class PopularListingSerializer(serializers.ModelSerializer):
    view_count = serializers.IntegerField(read_only=True)

    class Meta:
        model = Listing
        fields = ("id", "title", "view_count")
