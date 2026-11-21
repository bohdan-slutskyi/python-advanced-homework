from django.contrib import admin
from django.urls import include, path
from drf_spectacular.views import SpectacularAPIView, SpectacularSwaggerView
from rest_framework.routers import DefaultRouter
from rest_framework_simplejwt.views import TokenRefreshView

from apps.accounts.views import LoginView, LogoutView, MeView, RegisterView
from apps.bookings.views import BookingViewSet
from apps.listings.views import ListingViewSet
from apps.reviews.views import ListingReviewsView, ReviewViewSet
from apps.statistics.views import (
    PopularListingsView,
    PopularSearchesView,
    SearchHistoryView,
    ViewHistoryView,
)

router = DefaultRouter()
router.register("listings", ListingViewSet, basename="listing")
router.register("bookings", BookingViewSet, basename="booking")
router.register("reviews", ReviewViewSet, basename="review")

urlpatterns = [
    path("api/schema/", SpectacularAPIView.as_view(), name="schema"),
    path(
        "api/docs/", SpectacularSwaggerView.as_view(url_name="schema"), name="api_docs"
    ),
    path("admin/", admin.site.urls),
    path("api/auth/register/", RegisterView.as_view(), name="register"),
    path("api/auth/login/", LoginView.as_view(), name="login"),
    path("api/auth/refresh/", TokenRefreshView.as_view(), name="token_refresh"),
    path("api/auth/logout/", LogoutView.as_view(), name="logout"),
    path("api/auth/me/", MeView.as_view(), name="me"),
    path(
        "api/statistics/search-history/",
        SearchHistoryView.as_view(),
        name="search-history",
    ),
    path(
        "api/statistics/view-history/",
        ViewHistoryView.as_view(),
        name="view-history",
    ),
    path(
        "api/statistics/popular-searches/",
        PopularSearchesView.as_view(),
        name="popular-searches",
    ),
    path(
        "api/statistics/popular-listings/",
        PopularListingsView.as_view(),
        name="popular-listings",
    ),
    path(
        "api/listings/<int:pk>/reviews/",
        ListingReviewsView.as_view(),
        name="listing-reviews",
    ),
    path("api/", include(router.urls)),
]
